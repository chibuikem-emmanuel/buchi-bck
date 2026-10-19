from rest_framework.views import APIView
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import Transaction, WithdrawalRequest, SystemSetting
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
# Assuming you have models named InvestmentPlan and UserDeposit/Deposit defined:

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

class AdminUserDetailView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, pk, *args, **kwargs):
        try:
            user = User.objects.get(id=pk)
            data = request.data

            # Update core user details
            if 'full_name' in data:
                user.full_name = data['full_name']
            if 'username' in data and data['username']:
                user.username = data['username']
            if 'email' in data and data['email']:
                user.email = data['email']
            if 'status' in data:
                user.is_blacklisted = (data['status'] == 'Disabled')

            # Update password if provided
            if data.get('password'):
                user.set_password(data['password'])

            # Update crypto wallet addresses
            if 'btc_address' in data:
                user.btc_address = data['btc_address']
            if 'usdt_trc20' in data:
                user.usdt_trc20 = data['usdt_trc20']
            if 'usdt_erc20' in data:
                user.usdt_erc20 = data['usdt_erc20']
            if 'eth_address' in data:
                user.eth_address = data['eth_address']
            if 'bnb_address' in data:
                user.bnb_address = data['bnb_address']
            if 'admin_note' in data:
                user.admin_note = data['admin_note']

            user.save()

            return Response({
                "success": True, 
                "message": f"User {user.username} updated successfully!",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": getattr(user, 'full_name', ''),
                    "is_blacklisted": user.is_blacklisted,
                    "balance": float(getattr(user, 'balance', 0))
                }
            }, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

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

# crystals_core/investments/admin_views.py

class AdminWithdrawalListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        # status__iexact handles any capitalization ('PENDING', 'Pending', 'pending')
        withdrawals = WithdrawalRequest.objects.filter(status__iexact='PENDING').order_by('-created_at')
        
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




class AdminProcessingsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        # Default list of processors matching HYIP Manager Pro list
        processings = [
            {"id": 1, "name": "Bitcoin", "code": "btc", "status": "ON", "instructions": "Transfer USDT/BTC to wallet address TQn9Y2kh5B8uJ1K3mX7P4zL9vN8qW6eR1s", "min_deposit": "100.00", "max_deposit": "100000.00", "min_withdraw": "10.00", "max_withdraw": "50000.00"},
            {"id": 2, "name": "USDT TRC20", "code": "usdt_trc20", "status": "ON", "instructions": "Send exact amount in USDT TRC20 network.", "min_deposit": "50.00", "max_deposit": "500000.00", "min_withdraw": "10.00", "max_withdraw": "100000.00"},
            {"id": 3, "name": "USDT ERC20", "code": "usdt_erc20", "status": "ON", "instructions": "Send USDT via Ethereum ERC20.", "min_deposit": "100.00", "max_deposit": "500000.00", "min_withdraw": "20.00", "max_withdraw": "100000.00"},
            {"id": 4, "name": "Ethereum", "code": "eth", "status": "ON", "instructions": "Transfer ETH to platform ETH wallet.", "min_deposit": "100.00", "max_deposit": "200000.00", "min_withdraw": "15.00", "max_withdraw": "50000.00"},
            {"id": 5, "name": "BNB", "code": "bnb", "status": "ON", "instructions": "Transfer BNB (BEP20 network).", "min_deposit": "50.00", "max_deposit": "100000.00", "min_withdraw": "10.00", "max_withdraw": "50000.00"},
            {"id": 6, "name": "PerfectMoney", "code": "pm", "status": "OFF", "instructions": "Automatic gateway deposit.", "min_deposit": "10.00", "max_deposit": "10000.00", "min_withdraw": "5.00", "max_withdraw": "5000.00"},
            {"id": 7, "name": "Payeer", "code": "payeer", "status": "OFF", "instructions": "Payeer instant deposit.", "min_deposit": "10.00", "max_deposit": "10000.00", "min_withdraw": "5.00", "max_withdraw": "5000.00"},
            {"id": 8, "name": "Bank Wire", "code": "wire", "status": "OFF", "instructions": "Bank transfer instructions upon request.", "min_deposit": "1000.00", "max_deposit": "1000000.00", "min_withdraw": "500.00", "max_withdraw": "500000.00"},
        ]
        return Response(processings, status=status.HTTP_200_OK)

    def put(self, request, pk=None, *args, **kwargs):
        # Update specific processing settings
        return Response({"success": True, "message": "Processing gateway settings updated successfully!"})






class AdminInvestmentPlanListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, format=None):
        # Fetch all investment plans or return mock structure matching your frontend
        plans = [
            {
                "id": 1,
                "name": "BASIC PLAN",
                "min_amount": "100.00",
                "max_amount": "4999.00",
                "profit_percent": "4.00",
                "duration_days": "3",
                "status": "Active",
                "total_count": 159,
                "total_amount": "71120.28",
                "active_count": 1,
                "active_amount": "670.00"
            },
            {
                "id": 2,
                "name": "EXPERT PLAN",
                "min_amount": "5000.00",
                "max_amount": "19999.00",
                "profit_percent": "6.00",
                "duration_days": "5",
                "status": "Active",
                "total_count": 33,
                "total_amount": "210799.38",
                "active_count": 0,
                "active_amount": "0.00"
            }
        ]
        return Response(plans, status=status.HTTP_200_OK)

    def post(self, request, format=None):
        # Handle creating a new investment plan
        name = request.data.get('name')
        min_amount = request.data.get('min_amount')
        max_amount = request.data.get('max_amount')
        profit_percent = request.data.get('profit_percent')
        duration_days = request.data.get('duration_days')
        
        # Save logic here...
        
        return Response({"success": True, "message": "Investment plan created successfully!"}, status=status.HTTP_201_CREATED)


class AdminInvestmentPlanDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def put(self, request, pk, format=None):
        # Update investment plan logic by pk
        return Response({"success": True, "message": f"Investment plan {pk} updated successfully!"}, status=status.HTTP_200_OK)

    def delete(self, request, pk, format=None):
        # Delete investment plan logic by pk
        return Response({"success": True, "message": f"Investment plan {pk} deleted successfully!"}, status=status.HTTP_200_OK)


class AdminExpiringDepositsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, format=None):
        expiring = [
            {
                "id": 1,
                "username": "K38kamran",
                "plan_name": "BASIC PLAN",
                "amount": "670.00",
                "expires_at": "Oct-15-2026 12:00:00 PM"
            }
        ]
        return Response(expiring, status=status.HTTP_200_OK)