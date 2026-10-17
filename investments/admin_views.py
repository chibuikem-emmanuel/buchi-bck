# investments/admin_views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import InvestmentPlan, Transaction
from .serializers import InvestmentPlanSerializer, TransactionSerializer
from decimal import Decimal

from decimal import Decimal
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import InvestmentPlan, Transaction
from .serializers import InvestmentPlanSerializer, TransactionSerializer



User = get_user_model()

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff

class AdminCreditUserBalanceView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        amount_raw = request.data.get('amount')

        if not email or not amount_raw:
            return Response({'error': 'Email and amount are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = Decimal(str(amount_raw))
            target_user = User.objects.get(email=email)
            target_user.balance += amount
            target_user.save()

            Transaction.objects.create(
                user=target_user,
                transaction_type='DEPOSIT',
                amount=amount,
                status='APPROVED'
            )

            return Response({'success': True, 'message': f'Successfully credited ${amount} to {email}'})
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)



class AdminInvestmentPlanCreateUpdateView(generics.CreateAPIView, generics.UpdateAPIView):
    queryset = InvestmentPlan.objects.all()
    serializer_class = InvestmentPlanSerializer
    permission_classes = [IsAdminUser]

# class AdminCreditUserBalanceView(generics.GenericAPIView):
#     permission_classes = [IsAdminUser]

#     def post(self, request, *args, **kwargs):
#         email = request.data.get('email')
#         amount = request.data.get('amount')

#         if not email or not amount:
#             return Response({'error': 'Email and amount are required'}, status=status.HTTP_400_BAD_REQUEST)

#         try:
#             target_user = User.objects.get(email=email)
#             target_user.balance += float(amount)
#             target_user.save()

#             # Log transaction
#             Transaction.objects.create(
#                 user=target_user,
#                 transaction_type='DEPOSIT',
#                 amount=amount,
#                 status='APPROVED'
#             )

#             return Response({'success': True, 'message': f'Successfully credited ${amount} to {email}'})
#         except User.DoesNotExist:
#             return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

# 1. Admin Users Directory View
class AdminUserListView(generics.ListAPIView):
    queryset = User.objects.all().order_by('-date_joined')
    permission_classes = [IsAdminUser]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = [{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'balance': str(u.balance),
            'is_blacklisted': u.is_blacklisted if hasattr(u, 'is_blacklisted') else False,
            'phone_number': u.phone_number
        } for u in queryset]
        return Response(data)

# 2. Admin Toggle User Blacklist View
class AdminUserDetailView(generics.UpdateAPIView):
    queryset = User.objects.all()
    permission_classes = [IsAdminUser]

    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        is_blacklisted = request.data.get('is_blacklisted')
        if is_blacklisted is not None:
            user.is_blacklisted = is_blacklisted
            user.save()
        return Response({'success': True, 'message': 'User status updated successfully'})

# 3. Admin Global Transactions View
class AdminTransactionListView(generics.ListAPIView):
    queryset = Transaction.objects.all().order_by('-created_at')
    serializer_class = TransactionSerializer
    permission_classes = [IsAdminUser]

# 4. Admin Withdrawals Management View
class AdminWithdrawalListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        withdrawals = Transaction.objects.filter(transaction_type='WITHDRAWAL', status='PENDING')
        data = [{
            'id': w.id,
            'user': w.user.username,
            'amount': str(w.amount),
            'method': 'Crypto / Bank',
            'status': w.status
        } for w in withdrawals]
        return Response(data)

class AdminProcessWithdrawalView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        action = request.data.get('action') # 'approve' or 'reject'
        try:
            withdrawal = Transaction.objects.get(pk=pk, transaction_type='WITHDRAWAL')
            if action == 'approve':
                withdrawal.status = 'APPROVED'
                withdrawal.save()
            elif action == 'reject':
                withdrawal.status = 'REJECTED'
                withdrawal.save()
                withdrawal.user.balance += withdrawal.amount
                withdrawal.user.save()
            return Response({'success': True, 'message': f'Withdrawal {action}d successfully'})
        except Transaction.DoesNotExist:
            return Response({'error': 'Withdrawal transaction not found'}, status=404)




class AdminSystemSettingsView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({'platform_name': 'Crystals Investments', 'status': 'Active'})

    def post(self, request):
        platform_name = request.data.get('platform_name', 'Crystals Investments')
        # Save or apply settings as needed
        return Response({'success': True, 'message': f'Platform name updated to {platform_name}'})


