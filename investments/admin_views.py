from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import Transaction, WithdrawalRequest, SystemSetting
from decimal import Decimal

User = get_user_model()

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            (request.user.is_staff or request.user.is_superuser)
        )

class AdminUserListView(generics.ListAPIView):
    queryset = User.objects.all().order_by('-date_joined')
    permission_classes = [IsAdminUser]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = [{
            'id': u.id,
            'username': u.username,
            'email': u.email,
            'balance': float(u.balance) if hasattr(u, 'balance') and u.balance else 0.00,
            'is_blacklisted': getattr(u, 'is_blacklisted', False),
            'phone_number': getattr(u, 'phone_number', '') or ''
        } for u in queryset]
        return Response(data)

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

class AdminCreditUserBalanceView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        try:
            amount = float(request.data.get('amount', 0))
        except (ValueError, TypeError):
            return Response({'error': 'Invalid amount format'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            if hasattr(user, 'balance'):
                user.balance = float(user.balance) + amount
                user.save()
                
                Transaction.objects.create(
                    user=user,
                    transaction_type='DEPOSIT',
                    amount=amount,
                    status='APPROVED'
                )
                return Response({'message': f'Successfully credited ${amount:.2f} to {user.email}'})
            return Response({'error': 'User model missing balance field'}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({'error': 'User with this email not found'}, status=status.HTTP_404_NOT_FOUND)

class AdminTransactionListView(generics.ListAPIView):
    queryset = Transaction.objects.all().order_by('-created_at')
    permission_classes = [IsAdminUser]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = [{
            'id': t.id,
            'username': t.user.username if t.user else 'Unknown',
            'email': t.user.email if t.user else '',
            'type': t.transaction_type,
            'amount': float(t.amount),
            'status': t.status,
            'created_at': t.created_at
        } for t in queryset]
        return Response(data)

class AdminWithdrawalListView(generics.ListAPIView):
    queryset = WithdrawalRequest.objects.filter(status='PENDING').order_by('-created_at')
    permission_classes = [IsAdminUser]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = [{
            'id': w.id,
            'user_email': w.user.email if w.user else '',
            'username': w.user.username if w.user else '',
            'amount': float(w.amount),
            'method': getattr(w, 'method', 'USDT TRC20'),
            'created_at': w.created_at
        } for w in queryset]
        return Response(data)

class AdminProcessWithdrawalView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        withdrawal_id = kwargs.get('pk')
        action = request.data.get('action') # 'approve' or 'reject'
        try:
            withdrawal = WithdrawalRequest.objects.get(id=withdrawal_id)
            if action == 'approve':
                withdrawal.status = 'APPROVED'
            elif action == 'reject':
                withdrawal.status = 'REJECTED'
                if hasattr(withdrawal.user, 'balance'):
                    withdrawal.user.balance = float(withdrawal.user.balance) + float(withdrawal.amount)
                    withdrawal.user.save()
            withdrawal.save()
            return Response({'message': f'Withdrawal successfully {action}d'})
        except WithdrawalRequest.DoesNotExist:
            return Response({'error': 'Withdrawal request not found'}, status=status.HTTP_404_NOT_FOUND)






class AdminSystemSettingsView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        setting, _ = SystemSetting.objects.get_or_create(
            id=1, 
            defaults={"platform_name": "Crystals Investments"}
        )
        return Response({"platform_name": setting.platform_name})

    def put(self, request, *args, **kwargs):
        setting, _ = SystemSetting.objects.get_or_create(
            id=1, 
            defaults={"platform_name": "Crystals Investments"}
        )
        platform_name = request.data.get('platform_name')
        if platform_name:
            setting.platform_name = platform_name
            setting.save()
            return Response({"success": True, "message": "System settings updated successfully", "platform_name": setting.platform_name})
        return Response({"error": "platform_name is required"}, status=status.HTTP_400_BAD_REQUEST)