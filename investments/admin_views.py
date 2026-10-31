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
from .models import ProcessingGateway
from .models import Deposit, Withdrawal
from django.db import transaction
from django.db.models import Q
from django.db.models import Sum, Count
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
        data = []
        for u in queryset:
            # Check if user has a related profile model or attributes
            profile = getattr(u, 'profile', u)
            
            # Calculate total approved and pending/active deposits
            total_deposit = u.deposits.filter(status='APPROVED').aggregate(Sum('amount'))['amount__sum'] or 0.00
            active_deposit = u.deposits.filter(status='PENDING').aggregate(Sum('amount'))['amount__sum'] or 0.00
            
            data.append({
                'id': u.id,
                'username': u.username,
                'email': u.email,
                'full_name': f"{u.first_name} {u.last_name}".strip(),
                'status': 'Active' if u.is_active else 'Disabled',
                'is_active': u.is_active,
                'is_staff': u.is_staff,
                'balance': float(getattr(u, 'balance', 0.00)),
                'total_deposit': float(total_deposit),
                'active_deposit': float(active_deposit),
                'is_blacklisted': getattr(u, 'is_blacklisted', False),
                'phone_number': getattr(u, 'phone_number', '') or '',
                'btc_address': getattr(profile, 'btc_address', ''),
                'usdt_trc20': getattr(profile, 'usdt_trc20', ''),
                'usdt_erc20': getattr(profile, 'usdt_erc20', ''),
                'eth_address': getattr(profile, 'eth_address', ''),
                'bnb_address': getattr(profile, 'bnb_address', ''),
                'admin_note': getattr(profile, 'admin_note', ''),
            })
        return Response(data)

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
            
            # Basic credentials
            if 'username' in data and data['username'] is not None:
                user.username = data['username']
            if 'email' in data and data['email'] is not None:
                user.email = data['email']
                
            # Handle full_name conversion to first_name/last_name
            if 'full_name' in data and data['full_name'] is not None:
                name_parts = str(data['full_name']).strip().split(' ', 1)
                user.first_name = name_parts[0]
                user.last_name = name_parts[1] if len(name_parts) > 1 else ''
            
            # Fallback for explicit first/last name
            first_name = data.get('first_name') or data.get('firstName')
            if first_name is not None:
                user.first_name = first_name
            last_name = data.get('last_name') or data.get('lastName')
            if last_name is not None:
                user.last_name = last_name

            # Handle status -> is_active
            if 'status' in data:
                status_val = str(data['status']).lower()
                user.is_active = status_val in ['active', 'true', '1', 'enabled', 'true']
            elif 'is_active' in data:
                user.is_active = bool(data['is_active'])

            # Handle crypto wallets and admin notes (checking on user or related profile)
            target_obj = getattr(user, 'profile', user)
            fields_to_update = [
                'btc_address', 'usdt_trc20', 'usdt_erc20', 
                'eth_address', 'bnb_address', 'admin_note'
            ]
            for field in fields_to_update:
                if field in data and hasattr(target_obj, field):
                    setattr(target_obj, field, data[field])
            
            if hasattr(user, 'profile'):
                user.profile.save()

            # Temporary password assignment
            password = data.get('password') or data.get('temp_password')
            if password and str(password).strip() != '':
                user.set_password(str(password).strip())
                
            user.save()
            print(f"SUCCESS: User {pk} updated successfully.")
            return Response({"success": True, "message": "User updated successfully!"}, status=status.HTTP_200_OK)
            
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
    




class AdminAnalyticsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        try:
            total_users = User.objects.count()
            
            approved_deposits = Deposit.objects.filter(status='APPROVED').aggregate(total=Sum('amount'))['total']
            total_deposits_amount = approved_deposits if approved_deposits is not None else 0.00
            
            pending_deposits_count = Deposit.objects.filter(status='PENDING').count()
            pending_dep_amt = Deposit.objects.filter(status='PENDING').aggregate(total=Sum('amount'))['total']
            pending_deposits_amount = pending_dep_amt if pending_dep_amt is not None else 0.00

            approved_withdrawals = Withdrawal.objects.filter(status='APPROVED').aggregate(total=Sum('amount'))['total']
            total_withdrawals_amount = approved_withdrawals if approved_withdrawals is not None else 0.00
            
            pending_withdrawals_count = Withdrawal.objects.filter(status='PENDING').count()
            pending_wth_amt = Withdrawal.objects.filter(status='PENDING').aggregate(total=Sum('amount'))['total']
            pending_withdrawals_amount = pending_wth_amt if pending_wth_amt is not None else 0.00

            total_plans_count = InvestmentPlan.objects.count()
            
            # FIXED: Use is_active=True instead of status='Active'
            active_plans_count = InvestmentPlan.objects.filter(is_active=True).count()

            net_platform_volume = float(total_deposits_amount) - float(total_withdrawals_amount)

            return Response({
                "overview": {
                    "totalUsers": total_users,
                    "netPlatformVolume": f"{net_platform_volume:.2f}",
                    "totalPlans": total_plans_count,
                    "activePlans": active_plans_count,
                },
                "deposits": {
                    "totalApproved": f"{float(total_deposits_amount):.2f}",
                    "pendingCount": pending_deposits_count,
                    "pendingAmount": f"{float(pending_deposits_amount):.2f}",
                },
                "withdrawals": {
                    "totalApproved": f"{float(total_withdrawals_amount):.2f}",
                    "pendingCount": pending_withdrawals_count,
                    "pendingAmount": f"{float(pending_withdrawals_amount):.2f}",
                }
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            print("Analytics Error:", str(e))
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        



class AdminWithdrawalsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        withdrawals = Withdrawal.objects.select_related('user').all()
        data = [{
            "id": w.id,
            "username": w.user.username if w.user else "Unknown",
            "user_email": w.user.email if w.user else "",
            "gateway": w.gateway,
            "amount": str(w.amount),
            "wallet_address": w.wallet_address,
            "status": w.status,
            "created_at": w.created_at.strftime('%Y-%m-%d %H:%M'),
        } for w in withdrawals]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, pk=None, *args, **kwargs):
        """Action endpoint to approve or reject a withdrawal"""
        withdrawal_id = request.data.get('withdrawal_id') or pk
        action = request.data.get('action') # 'approve' or 'reject'

        if not withdrawal_id or not action:
            return Response({"error": "withdrawal_id and action are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                wth = Withdrawal.objects.select_for_update().get(pk=withdrawal_id)
                if wth.status != 'PENDING':
                    return Response({"error": f"Withdrawal is already {wth.status.lower()}."}, status=status.HTTP_400_BAD_REQUEST)

                if action == 'approve':
                    wth.status = 'APPROVED'
                    wth.save()
                    return Response({"success": True, "message": f"Withdrawal #{wth.id} approved successfully!"})

                elif action == 'reject':
                    wth.status = 'REJECTED'
                    # Refund balance back to user
                    user = wth.user
                    if hasattr(user, 'profile'):
                        user.profile.balance += wth.amount
                        user.profile.save()
                    elif hasattr(user, 'balance'):
                        user.balance += wth.amount
                        user.save()
                    wth.save()
                    return Response({"success": True, "message": f"Withdrawal #{wth.id} rejected and balance refunded."})

                return Response({"error": "Invalid action parameter."}, status=status.HTTP_400_BAD_REQUEST)

        except Withdrawal.DoesNotExist:
            return Response({"error": "Withdrawal record not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)




class AdminProcessingsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        # Auto-seed default processors if the table is empty
        if not ProcessingGateway.objects.exists():
            defaults = [
                {"name": "Bitcoin", "code": "btc", "status": "ON", "instructions": "Transfer Bitcoin to official wallet address.", "min_deposit": "100.00", "max_deposit": "100000.00", "min_withdraw": "10.00", "max_withdraw": "50000.00"},
                {"name": "USDT TRC20", "code": "usdt_trc20", "status": "ON", "instructions": "Send exact amount in USDT TRC20 network.", "min_deposit": "50.00", "max_deposit": "500000.00", "min_withdraw": "10.00", "max_withdraw": "100000.00"},
                {"name": "USDT ERC20", "code": "usdt_erc20", "status": "ON", "instructions": "Send USDT via Ethereum ERC20.", "min_deposit": "100.00", "max_deposit": "500000.00", "min_withdraw": "20.00", "max_withdraw": "100000.00"},
                {"name": "Ethereum", "code": "eth", "status": "ON", "instructions": "Transfer ETH to platform ETH wallet.", "min_deposit": "100.00", "max_deposit": "200000.00", "min_withdraw": "15.00", "max_withdraw": "50000.00"},
                {"name": "BNB", "code": "bnb", "status": "ON", "instructions": "Transfer BNB (BEP20 network).", "min_deposit": "50.00", "max_deposit": "100000.00", "min_withdraw": "10.00", "max_withdraw": "50000.00"},
                {"name": "PerfectMoney", "code": "pm", "status": "OFF", "instructions": "Automatic gateway deposit.", "min_deposit": "10.00", "max_deposit": "10000.00", "min_withdraw": "5.00", "max_withdraw": "5000.00"},
                {"name": "Payeer", "code": "payeer", "status": "OFF", "instructions": "Payeer instant deposit.", "min_deposit": "10.00", "max_deposit": "10000.00", "min_withdraw": "5.00", "max_withdraw": "5000.00"},
                {"name": "Bank Wire", "code": "wire", "status": "OFF", "instructions": "Bank transfer instructions upon request.", "min_deposit": "1000.00", "max_deposit": "1000000.00", "min_withdraw": "500.00", "max_withdraw": "500000.00"},
            ]
            for item in defaults:
                ProcessingGateway.objects.create(**item)

        gateways = ProcessingGateway.objects.all().order_by('id')
        data = [{
            "id": g.id,
            "name": g.name,
            "code": g.code,
            "status": g.status,
            "instructions": g.instructions or "",
            "min_deposit": str(g.min_deposit),
            "max_deposit": str(g.max_deposit),
            "min_withdraw": str(g.min_withdraw),
            "max_withdraw": str(g.max_withdraw),
        } for g in gateways]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            name = data.get('name', 'Custom Gateway')
            code = data.get('code') or name.lower().replace(' ', '_')
            
            gateway = ProcessingGateway.objects.create(
                name=name,
                code=code,
                status=str(data.get('status', 'ON')).upper(),
                instructions=data.get('instructions', ''),
                min_deposit=data.get('min_deposit') or data.get('minDeposit') or 0.00,
                max_deposit=data.get('max_deposit') or data.get('maxDeposit') or 0.00,
                min_withdraw=data.get('min_withdraw') or data.get('minWithdraw') or 0.00,
                max_withdraw=data.get('max_withdraw') or data.get('maxWithdraw') or 0.00,
            )
            return Response({
                "success": True, 
                "message": "Processing gateway created successfully!",
                "id": gateway.id
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None, *args, **kwargs):
        if not pk:
            return Response({"error": "Gateway ID required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            gateway = ProcessingGateway.objects.get(pk=pk)
            data = request.data
            
            if 'name' in data and data['name']:
                gateway.name = data['name']
            if 'code' in data and data['code']:
                gateway.code = data['code']
            if 'status' in data:
                gateway.status = str(data['status']).upper()
            if 'instructions' in data:
                gateway.instructions = data['instructions']

            # Limit attributes (supporting camelCase and snake_case)
            min_dep = data.get('min_deposit') or data.get('minDeposit')
            if min_dep is not None:
                gateway.min_deposit = min_dep

            max_dep = data.get('max_deposit') or data.get('maxDeposit')
            if max_dep is not None:
                gateway.max_deposit = max_dep

            min_wth = data.get('min_withdraw') or data.get('minWithdraw')
            if min_wth is not None:
                gateway.min_withdraw = min_wth

            max_wth = data.get('max_withdraw') or data.get('maxWithdraw')
            if max_wth is not None:
                gateway.max_withdraw = max_wth
                
            gateway.save()
            return Response({"success": True, "message": "Processing gateway updated successfully!"}, status=status.HTTP_200_OK)
            
        except ProcessingGateway.DoesNotExist:
            return Response({"error": f"Gateway with ID {pk} not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_400_BAD_REQUEST)






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
    


class AdminDepositsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request, *args, **kwargs):
        user_id = request.query_params.get('user_id')
        deposits = Deposit.objects.select_related('user').all()
        
        # Filter by user_id if provided from the frontend dashboard
        if user_id:
            deposits = deposits.filter(user_id=user_id)

        data = [{
            "id": d.id,
            "username": d.user.username if d.user else "Unknown",
            "user_email": d.user.email if d.user else "",
            "gateway": d.gateway,
            "amount": str(d.amount),
            "transaction_id": d.transaction_id,
            "status": d.status,
            "created_at": d.created_at.strftime('%Y-%m-%d %H:%M'),
        } for d in deposits]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, pk=None, *args, **kwargs):
        deposit_id = request.data.get('deposit_id') or pk
        action = request.data.get('action')

        if not deposit_id or not action:
            return Response({"error": "deposit_id and action are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                dep = Deposit.objects.select_for_update().get(pk=deposit_id)
                if dep.status != 'PENDING':
                    return Response({"error": f"Deposit is already {dep.status.lower()}."}, status=status.HTTP_400_BAD_REQUEST)

                if action == 'approve':
                    dep.status = 'APPROVED'
                    user = dep.user
                    if hasattr(user, 'profile'):
                        user.profile.balance += dep.amount
                        user.profile.save()
                    elif hasattr(user, 'balance'):
                        user.balance += dep.amount
                        user.save()
                    dep.save()
                    return Response({"success": True, "message": f"Deposit #{dep.id} approved successfully!"})

                elif action == 'reject':
                    dep.status = 'REJECTED'
                    dep.save()
                    return Response({"success": True, "message": f"Deposit #{dep.id} has been rejected."})

                return Response({"error": "Invalid action parameter."}, status=status.HTTP_400_BAD_REQUEST)
        except Deposit.DoesNotExist:
            return Response({"error": "Deposit record not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        






# Define the instant referral bonus amount
INSTANT_SIGNUP_BONUS = Decimal('5.00')

class RegisterView(APIView):
    def post(self, request):
        data = request.data
        print(f"--- REGISTRATION PAYLOAD RECEIVED ---: {data}")  # DEBUG LOG

        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        phone_number = data.get('phone_number')
        country = data.get('country')
        payout_address = data.get('payout_address')
        referred_by_code = data.get('referred_by')

        print(f"--- REFERRED BY CODE EXTRACTED ---: {referred_by_code}")  # DEBUG LOG

        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already taken'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # 1. Create the new user account
                new_user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    phone_number=phone_number,
                    country=country,
                    usdt_trc20=payout_address
                )

                # 2. Process instant referral bonus if ref code was provided
                if referred_by_code:
                    clean_ref = referred_by_code.strip()
                    
                    # Find the referrer case-insensitively by email or username
                    referrer = User.objects.filter(
                        Q(email__iexact=clean_ref) | Q(username__iexact=clean_ref)
                    ).first()

                    print(f"--- REFERRER FOUND IN DB ---: {referrer}")  # DEBUG LOG

                    if referrer and referrer != new_user:
                        # Link the referral relationship
                        new_user.referred_by = referrer
                        new_user.save(update_fields=['referred_by'])

                        # Credit the referrer's balance and total referral commission earned
                        referrer.balance += INSTANT_SIGNUP_BONUS
                        referrer.referral_bonus_earned += INSTANT_SIGNUP_BONUS
                        referrer.save(update_fields=['balance', 'referral_bonus_earned'])

                        # Create an approved transaction log entry for transparency
                        Transaction.objects.create(
                            user=referrer,
                            amount=INSTANT_SIGNUP_BONUS,
                            type='REFERRAL_BONUS',
                            status='APPROVED',
                            method='SYSTEM_BONUS',
                            description=f'Instant referral bonus for user registration: {new_user.email}'
                        )
                        print(f"--- BONUS SUCCESSFULLY CREDITED TO {referrer.email} ---")  # DEBUG LOG
                    else:
                        print("--- WARNING: Referrer match failed or referrer is new_user ---")

        except Exception as e:
            print(f"--- ERROR IN REGISTRATION ATOMIC BLOCK ---: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({'message': 'Registration successful!'}, status=status.HTTP_201_CREATED)
    


class AdminWithdrawalDetailView(generics.RetrieveAPIView):
    queryset = WithdrawalRequest.objects.all()
    serializer_class = WithdrawalRequestSerializer
    permission_classes = [permissions.IsAdminUser]
    lookup_field = 'pk'



