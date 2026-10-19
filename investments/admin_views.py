from rest_framework.views import APIView
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

class AdminWithdrawalListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        withdrawals = WithdrawalRequest.objects.filter(status='PENDING').order_by('-created_at')
        
        data = []
        for w in withdrawals:
            data.append({
                'id': w.id,
                'user_email': getattr(w.user, 'email', '') if w.user else '',
                'username': getattr(w.user, 'username', '') if w.user else '',
                'amount': float(w.amount),
                'method': getattr(w, 'method', 'USDT TRC20'),
                'created_at': w.created_at.strftime("%Y-%m-%d %H:%M:%S") if hasattr(w, 'created_at') and w.created_at else ''
            })
            
        return Response(data, status=status.HTTP_200_OK)

class AdminProcessWithdrawalView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        action = request.data.get('action')  # 'approve' or 'reject'

        try:
            withdrawal = WithdrawalRequest.objects.get(id=pk)
            user = withdrawal.user

            if action == 'approve':
                withdrawal.status = 'APPROVED'
                # Deduct balance upon approval
                if hasattr(user, 'balance'):
                    current_bal = float(user.balance)
                    if current_bal >= float(withdrawal.amount):
                        user.balance = current_bal - float(withdrawal.amount)
                        user.save()

            elif action == 'reject':
                withdrawal.status = 'REJECTED'

            withdrawal.save()

            # Sync matching transaction log status
            Transaction.objects.filter(
                user=user, 
                transaction_type='WITHDRAWAL', 
                amount=withdrawal.amount, 
                status='PENDING'
            ).update(status=withdrawal.status)

            return Response({'success': True, 'message': f'Withdrawal successfully {action}d'})
        except WithdrawalRequest.DoesNotExist:
            return Response({'error': 'Withdrawal request not found'}, status=status.HTTP_404_NOT_FOUND)





class AdminSystemSettingsView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        setting = SystemSetting.load()
        return Response({"platform_name": setting.platform_name})

    def put(self, request, *args, **kwargs):
        return self.update_settings(request)

    def patch(self, request, *args, **kwargs):
        return self.update_settings(request)

    def update_settings(self, request):
        setting = SystemSetting.load()
        platform_name = request.data.get('platform_name')
        
        if platform_name:
            setting.platform_name = platform_name.strip()
            setting.save()
            return Response({
                "success": True, 
                "message": "System settings updated successfully", 
                "platform_name": setting.platform_name
            }, status=status.HTTP_200_OK)
            
        return Response(
            {"error": "platform_name field is required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )