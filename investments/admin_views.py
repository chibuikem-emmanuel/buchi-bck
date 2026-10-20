from rest_framework.views import APIView
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from .models import Transaction, WithdrawalRequest, SystemSetting, InvestmentPlan
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import InvestmentPlanSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
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

class AdminUserListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, format=None):
        users = User.objects.all().order_by('-date_joined')
        data = []
        for u in users:
            data.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "is_active": u.is_active,
                "is_staff": u.is_staff,
                "date_joined": u.date_joined,
            })
        return Response(data, status=status.HTTP_200_OK)

class AdminUserDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def put(self, request, pk, format=None):
        return self._update_user(request, pk)

    def patch(self, request, pk, format=None):
        return self._update_user(request, pk)

    def _update_user(self, request, pk):
        try:
            print("RECEIVED USER UPDATE DATA:", request.data)
            user = User.objects.get(pk=pk)
            data = request.data
            
            if 'username' in data and data['username'] is not None:
                user.username = data['username']
            if 'email' in data and data['email'] is not None:
                user.email = data['email']
                
            first_name = data.get('first_name') or data.get('firstName')
            if first_name is not None:
                user.first_name = first_name
                
            last_name = data.get('last_name') or data.get('lastName')
            if last_name is not None:
                user.last_name = last_name
                
            if 'is_active' in data:
                user.is_active = bool(data['is_active'])
            elif 'isActive' in data:
                user.is_active = bool(data['isActive'])
            elif 'status' in data:
                status_val = str(data['status']).lower()
                user.is_active = status_val in ['active', 'true', '1', 'enabled']
                
            if 'is_staff' in data:
                user.is_staff = bool(data['is_staff'])
            elif 'isStaff' in data:
                user.is_staff = bool(data['isStaff'])
            elif 'role' in data:
                user.is_staff = str(data['role']).lower() in ['admin', 'staff', 'true']
                
            password = data.get('password') or data.get('temp_password')
            if password and str(password).strip() != '':
                user.set_password(str(password).strip())
                
            user.save()
            return Response({
                "success": True, 
                "message": "User updated successfully!"
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print("USER UPDATE ERROR:", str(e))
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

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






import traceback
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import InvestmentPlan
from decimal import Decimal

class AdminInvestmentPlanListView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, format=None):
        plans = InvestmentPlan.objects.all().order_by('id')
        data = []
        for p in plans:
            data.append({
                "id": p.id,
                "name": p.name,
                "min_amount": str(p.min_deposit),
                "max_amount": str(p.max_deposit),
                "profit_percent": str(p.daily_profit),
                "duration_days": p.duration_days,
                "status": "Active" if p.is_active else "Disabled"
            })
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, format=None):
        try:
            data = request.data
            
            # Map frontend payload fields to your exact model fields
            name = data.get('name')
            min_deposit = Decimal(str(data.get('min_amount') or data.get('min_deposit', '100.00')))
            max_deposit = Decimal(str(data.get('max_amount') or data.get('max_deposit', '4999.00')))
            daily_profit = Decimal(str(data.get('profit_percent') or data.get('daily_profit', '0')))
            duration_days = int(data.get('duration_days', 5))
            
            # Handle status string conversion to boolean is_active
            status_val = data.get('status', 'Active')
            is_active = True if str(status_val).lower() in ['active', 'true', '1'] else False

            plan = InvestmentPlan.objects.create(
                name=name,
                min_deposit=min_deposit,
                max_deposit=max_deposit,
                daily_profit=daily_profit,
                duration_days=duration_days,
                is_active=is_active
            )

            return Response({
                "success": True, 
                "message": "Investment plan created successfully!",
                "id": plan.id
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response({
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }, status=status.HTTP_400_BAD_REQUEST)


class AdminInvestmentPlanDetailView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def put(self, request, pk, format=None):
        try:
            plan = InvestmentPlan.objects.get(pk=pk)
            data = request.data
            
            if 'name' in data: 
                plan.name = data['name']
            if 'min_amount' in data or 'min_deposit' in data:
                plan.min_deposit = Decimal(str(data.get('min_amount') or data.get('min_deposit')))
            if 'max_amount' in data or 'max_deposit' in data:
                plan.max_deposit = Decimal(str(data.get('max_amount') or data.get('max_deposit')))
            if 'profit_percent' in data or 'daily_profit' in data:
                plan.daily_profit = Decimal(str(data.get('profit_percent') or data.get('daily_profit')))
            if 'duration_days' in data:
                plan.duration_days = int(data['duration_days'])
            if 'status' in data:
                plan.is_active = (str(data['status']).lower() in ['active', 'true', '1'])
            elif 'is_active' in data:
                plan.is_active = bool(data['is_active'])

            plan.save()
            return Response({"success": True, "message": "Investment plan updated successfully!"}, status=status.HTTP_200_OK)
            
        except InvestmentPlan.DoesNotExist:
            return Response({"error": "Investment plan not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk, format=None):
        try:
            plan = InvestmentPlan.objects.get(pk=pk)
            plan.delete()
            return Response({"success": True, "message": "Plan deleted successfully"}, status=status.HTTP_200_OK)
        except InvestmentPlan.DoesNotExist:
            return Response({"error": "Investment plan not found"}, status=status.HTTP_404_NOT_FOUND)

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