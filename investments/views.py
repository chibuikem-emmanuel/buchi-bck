from rest_framework import generics, permissions, serializers
from .models import InvestmentPlan, UserInvestment, Transaction, WithdrawalRequest
from .serializers import InvestmentPlanSerializer, UserInvestmentSerializer, TransactionSerializer
from datetime import timedelta
from django.utils import timezone

from decimal import Decimal
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Transaction, InvestmentPlan
from .serializers import TransactionSerializer, InvestmentPlanSerializer

class InvestmentPlanListView(generics.ListAPIView):
    queryset = InvestmentPlan.objects.filter(is_active=True)
    serializer_class = InvestmentPlanSerializer
    permission_classes = [permissions.AllowAny]

class UserInvestmentCreateView(generics.CreateAPIView):
    serializer_class = UserInvestmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        plan = serializer.validated_data['plan']
        amount = serializer.validated_data['amount']
        user = self.request.user

        if user.balance < amount:
            raise serializers.ValidationError("Insufficient balance for this investment.")

        user.balance -= amount
        user.total_invested += amount
        user.save()

        expected_return = amount + (amount * (plan.daily_profit / 100) * plan.duration_days)
        end_date = timezone.now() + timedelta(days=plan.duration_days)

        serializer.save(user=user, expected_return=expected_return, end_date=end_date)

class TransactionListCreateView(generics.ListCreateAPIView):
    serializer_class = TransactionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)



# investments/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Transaction, InvestmentPlan
from .serializers import TransactionSerializer, InvestmentPlanSerializer

class InvestmentPlanListView(generics.ListAPIView):
    queryset = InvestmentPlan.objects.all()
    serializer_class = InvestmentPlanSerializer
    permission_classes = [permissions.AllowAny]

class UserDepositCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            amount = float(request.data.get('amount', 0))
            method = request.data.get('method', 'USDT TRC20')
        except (ValueError, TypeError):
            return Response({"error": "Invalid deposit amount"}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({"error": "Amount must be greater than zero"}, status=status.HTTP_400_BAD_REQUEST)

        # Log pending transaction for admin review
        tx = Transaction.objects.create(
            user=request.user,
            transaction_type='DEPOSIT',
            amount=amount,
            payment_method=method,
            status='PENDING'
        )

        return Response({
            "success": True, 
            "message": f"Deposit request of ${amount:.2f} submitted! Awaiting admin confirmation.",
            "transaction_id": tx.id
        })

class UserWithdrawalCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            amount = float(request.data.get('amount', 0))
            method = request.data.get('method', 'USDT TRC20')
        except (ValueError, TypeError):
            return Response({"error": "Invalid withdrawal amount"}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({"error": "Amount must be greater than zero"}, status=status.HTTP_400_BAD_REQUEST)

        user_balance = float(getattr(request.user, 'balance', 0))
        if user_balance < amount:
            return Response({"error": "Insufficient account balance"}, status=status.HTTP_400_BAD_REQUEST)

        # Create pending withdrawal request for admin dashboard
        withdrawal = WithdrawalRequest.objects.create(
            user=request.user,
            amount=amount,
            method=method,
            status='PENDING'
        )

        # Log associated transaction record
        Transaction.objects.create(
            user=request.user,
            transaction_type='WITHDRAWAL',
            amount=amount,
            payment_method=method,
            status='PENDING'
        )

        return Response({
            "success": True, 
            "message": f"Withdrawal request of ${amount:.2f} submitted successfully!",
            "withdrawal_id": withdrawal.id
        })








# investments/views.py (Add this view)
class UserInvestmentCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        plan_id = request.data.get('plan_id')
        amount = float(request.data.get('amount', 0))

        try:
            plan = InvestmentPlan.objects.get(pk=plan_id)
            if request.user.balance < amount:
                return Response({'error': 'Insufficient balance for this investment'}, status=status.HTTP_400_BAD_REQUEST)

            if amount < float(plan.min_amount) or (plan.max_amount and amount > float(plan.max_amount)):
                return Response({'error': f'Amount must be between ${plan.min_amount} and ${plan.max_amount or "Unlimited"}'}, status=status.HTTP_400_BAD_REQUEST)

            # Deduct balance and create investment/transaction
            request.user.balance -= amount
            request.user.total_invested += amount
            request.user.save()

            Transaction.objects.create(
                user=request.user,
                transaction_type='INVESTMENT',
                amount=amount,
                status='APPROVED'
            )

            return Response({'success': True, 'message': f'Successfully invested ${amount} into {plan.name}!'})
        except InvestmentPlan.DoesNotExist:
            return Response({'error': 'Investment plan not found'}, status=status.HTTP_404_NOT_FOUND)




# investments/views.py


class InvestmentPlanListView(generics.ListAPIView):
    queryset = InvestmentPlan.objects.all()
    serializer_class = InvestmentPlanSerializer
    permission_classes = [permissions.AllowAny]

class UserDepositCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            amount = Decimal(str(request.data.get('amount', 0)))
            if amount <= 0:
                return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Immediately credit user balance upon deposit submission for seamless testing
            request.user.balance += amount
            request.user.save()

            txn = Transaction.objects.create(
                user=request.user,
                transaction_type='DEPOSIT',
                amount=amount,
                status='APPROVED'
            )
            return Response({
                'success': True, 
                'message': 'Deposit successful! Balance updated.', 
                'new_balance': str(request.user.balance)
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class UserWithdrawalCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            amount = Decimal(str(request.data.get('amount', 0)))
            if amount <= 0:
                return Response({'error': 'Invalid amount'}, status=status.HTTP_400_BAD_REQUEST)
                
            if request.user.balance < amount:
                return Response({'error': 'Insufficient account balance'}, status=status.HTTP_400_BAD_REQUEST)

            request.user.balance -= amount
            request.user.save()

            txn = Transaction.objects.create(
                user=request.user,
                transaction_type='WITHDRAWAL',
                amount=amount,
                status='PENDING'
            )
            return Response({'success': True, 'message': 'Withdrawal request submitted'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)