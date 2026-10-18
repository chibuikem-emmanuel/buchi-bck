from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import Transaction
from decimal import Decimal

User = get_user_model()

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)

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
            'is_blacklisted': u.is_blacklisted,
            'phone_number': u.phone_number or ''
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

class AdminTransactionListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        queryset = Transaction.objects.all().order_by('-created_at')
        tx_type = request.query_params.get('type')
        if tx_type and tx_type != 'all':
            queryset = queryset.filter(transaction_type__iexact=tx_type)

        data = [{
            'id': t.id,
            'username': t.user.username,
            'transaction_type': t.transaction_type,
            'amount': str(t.amount),
            'status': t.status,
            'date': t.created_at.strftime('%b-%d-%Y %I:%M:%S %p')
        } for t in queryset]
        return Response(data)

class AdminWithdrawalListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        withdrawals = Transaction.objects.filter(transaction_type='WITHDRAWAL', status='PENDING').order_by('-created_at')
        data = [{
            'id': w.id,
            'user': w.user.username,
            'amount': str(w.amount),
            'status': w.status
        } for w in withdrawals]
        return Response(data)

class AdminProcessWithdrawalView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        action = request.data.get('action') 
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
            return Response({'error': 'Withdrawal transaction not found'}, status=status.HTTP_404_NOT_FOUND)
        



from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import Transaction, WithdrawalRequest
from decimal import Decimal

User = get_user_model()

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser))

class AdminUserListView(generics.ListAPIView):
    queryset = User.objects.all().order_by('-date_joined')
    permission_classes = [IsAdminUser]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = [{
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "balance": float(u.balance) if hasattr(u, 'balance') and u.balance else 0.00,
            "is_blacklisted": getattr(u, 'is_blacklisted', False),
            "phone_number": getattr(u, 'phone_number', '')
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
        return Response({"success": True, "message": "User status updated successfully"})

class AdminCreditUserBalanceView(generics.GenericAPIView):
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        try:
            amount = float(request.data.get('amount', 0))
        except (ValueError, TypeError):
            return Response({"error": "Invalid amount format"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            if hasattr(user, 'balance'):
                user.balance = float(user.balance) + amount
                user.save()
                
                Transaction.objects.create(
                    user=user,
                    type='credit',
                    amount=amount,
                    status='approved'
                )
                return Response({"message": f"Successfully credited ${amount:.2f} to {user.email}"})
            return Response({"error": "User model missing balance field"}, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

class AdminWithdrawalListView(generics.ListAPIView):
    queryset = WithdrawalRequest.objects.filter(status='pending').order_by('-created_at')
    permission_classes = [IsAdminUser]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        data = [{
            "id": w.id,
            "user_email": w.user.email,
            "username": w.user.username,
            "amount": float(w.amount),
            "method": getattr(w, 'method', 'USDT TRC20'),
            "created_at": w.created_at
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
                withdrawal.status = 'approved'
            elif action == 'reject':
                withdrawal.status = 'rejected'
                if hasattr(withdrawal.user, 'balance'):
                    withdrawal.user.balance = float(withdrawal.user.balance) + float(withdrawal.amount)
                    withdrawal.user.save()
            withdrawal.save()
            return Response({"message": f"Withdrawal successfully {action}d"})
        except WithdrawalRequest.DoesNotExist:
            return Response({"error": "Withdrawal request not found"}, status=status.HTTP_404_NOT_FOUND)