from rest_framework import generics, permissions, serializers
from .models import InvestmentPlan, UserInvestment, Transaction, Withdrawal, WithdrawalRequest
from .serializers import InvestmentPlanSerializer, UserInvestmentSerializer, TransactionSerializer
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from rest_framework.views import APIView
from accounts.serializers import RegisterSerializer
from rest_framework import serializers

from django.db import transaction

from decimal import Decimal
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Transaction, InvestmentPlan, WithdrawalRequest, Deposit
from .serializers import TransactionSerializer, InvestmentPlanSerializer
from django.contrib.auth import get_user_model

User = get_user_model()

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

# crystals_core/investments/views.py

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

        # 1. Create the Pending Withdrawal Request for the Admin Dashboard
        withdrawal = WithdrawalRequest.objects.create(
            user=request.user,
            amount=amount,
            method=method,
            status='PENDING' # MUST BE EXACTLY UPPERCASE 'PENDING'
        )

        # 2. Also log the Transaction record
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

# crystals_core/investments/views.py

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

        # MUST CREATE WithdrawalRequest ENTRY FOR ADMIN DASHBOARD
        withdrawal = WithdrawalRequest.objects.create(
            user=request.user,
            amount=amount,
            method=method,
            status='PENDING' # Upper case PENDING
        )

        # ALSO CREATE Transaction RECORD FOR USER DASHBOARD
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
            "id": withdrawal.id
        })






class UserTransactionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Fetch transactions for the authenticated user only
        transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
        
        data = []
        for tx in transactions:
            data.append({
                'id': tx.id,
                'type': tx.transaction_type,
                'amount': float(tx.amount),
                'status': tx.status,
                'method': tx.payment_method or 'USDT TRC20',
                'date': tx.created_at.strftime("%b-%d-%Y %I:%M %p") if tx.created_at else ''
            })
            
        return Response(data, status=status.HTTP_200_OK)

class UserTransactionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Fetch transactions for the authenticated user only
        transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
        
        data = []
        for tx in transactions:
            data.append({
                'id': tx.id,
                'type': tx.transaction_type,
                'amount': float(tx.amount),
                'status': tx.status,
                'method': tx.payment_method or 'USDT TRC20',
                'date': tx.created_at.strftime("%b-%d-%Y %I:%M %p") if tx.created_at else ''
            })
            
        return Response(data, status=status.HTTP_200_OK)



class UserDepositsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Fetch only the logged-in user's deposits
        deposits = Deposit.objects.filter(user=request.user)
        data = [{
            "id": d.id,
            "gateway": d.gateway,
            "amount": str(d.amount),
            "transaction_id": d.transaction_id,
            "status": d.status,
            "created_at": d.created_at.strftime('%Y-%m-%d %H:%M'),
        } for d in deposits]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        gateway = request.data.get('gateway')
        amount = request.data.get('amount')
        transaction_id = request.data.get('transaction_id')

        if not gateway or not amount or not transaction_id:
            return Response({"error": "All fields (gateway, amount, transaction_id) are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            deposit = Deposit.objects.create(
                user=request.user,
                gateway=gateway,
                amount=amount,
                transaction_id=transaction_id,
                status='PENDING'
            )
            return Response({"success": True, "message": "Deposit submitted successfully! Waiting for admin approval."}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        




class UserWithdrawalsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # Fetch only the logged-in user's withdrawals
        withdrawals = Withdrawal.objects.filter(user=request.user)
        data = [{
            "id": w.id,
            "gateway": w.gateway,
            "amount": str(w.amount),
            "wallet_address": w.wallet_address,
            "status": w.status,
            "created_at": w.created_at.strftime('%Y-%m-%d %H:%M'),
        } for w in withdrawals]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        gateway = request.data.get('gateway')
        amount = float(request.data.get('amount', 0))
        wallet_address = request.data.get('wallet_address')

        if not gateway or amount <= 0 or not wallet_address:
            return Response({"error": "Valid gateway, amount, and wallet address are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                user = request.user
                profile = getattr(user, 'profile', user) # Handles profile or direct balance field

                if float(profile.balance) < amount:
                    return Response({"error": "Insufficient balance for this withdrawal."}, status=status.HTTP_400_BAD_REQUEST)

                # Deduct balance immediately upon request (held in escrow)
                profile.balance -= amount
                profile.save()

                withdrawal = Withdrawal.objects.create(
                    user=user,
                    gateway=gateway,
                    amount=amount,
                    wallet_address=wallet_address,
                    status='PENDING'
                )
                return Response({"success": True, "message": "Withdrawal request submitted successfully!"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)




User = get_user_model()

# Define the instant referral bonus amount
INSTANT_SIGNUP_BONUS = Decimal('5.00')

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        referred_by_code = self.request.data.get('referred_by')
        print(f"--- PERFORM_CREATE TRIGGERED. REF ID: {referred_by_code} ---")

        with transaction.atomic():
            # 1. Save the new user using the DRF serializer
            new_user = serializer.save()

            # 2. Process instant referral bonus if ref ID was provided
            if referred_by_code:
                clean_ref = str(referred_by_code).strip()
                referrer = None
                
                # Check if the code is a valid number (User ID)
                if clean_ref.isdigit():
                    referrer = User.objects.filter(id=int(clean_ref)).first()

                print(f"--- REFERRER LOOKUP RESULT ---: {referrer}")

                if referrer and referrer != new_user:
                    # Link the referral relationship
                    new_user.referred_by = referrer
                    new_user.save(update_fields=['referred_by'])

                    # Credit the referrer's balance and total referral commission earned
                    referrer.balance += INSTANT_SIGNUP_BONUS
                    referrer.referral_bonus_earned += INSTANT_SIGNUP_BONUS
                    referrer.save(update_fields=['balance', 'referral_bonus_earned'])

                    # Safely create transaction record using valid model fields
                    try:
                        Transaction.objects.create(
                            user=referrer,
                            amount=INSTANT_SIGNUP_BONUS,
                            status='APPROVED'
                        )
                        print(f"--- $5.00 BONUS SUCCESSFULLY CREDITED & LOGGED FOR ID {referrer.id} ---")
                    except Exception as tx_err:
                        print(f"--- WARNING: Bonus credited, but transaction log failed: {tx_err} ---")
                else:
                    print("--- WARNING: Referrer match failed or referrer is new_user ---")