from decimal import Decimal
import uuid
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework import generics, permissions, serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.serializers import RegisterSerializer
from crystals_core.notifications import send_admin_alert, send_user_email
from .models import (
    ActiveInvestment,
    Deposit,
    InvestmentPlan,
    Transaction,
    UserInvestment,
    Withdrawal,
    WithdrawalRequest,
)
from .serializers import (
    InvestmentPlanSerializer,
    UserInvestmentSerializer,
)

User = get_user_model()
INSTANT_SIGNUP_BONUS = Decimal('5.00')


class InvestmentPlanListView(generics.ListAPIView):
    queryset = InvestmentPlan.objects.filter(is_active=True).order_by('id')
    serializer_class = InvestmentPlanSerializer
    permission_classes = [permissions.AllowAny]


class UserInvestmentCreateView(generics.CreateAPIView):
    serializer_class = UserInvestmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        plan = serializer.validated_data['plan']
        amount = Decimal(str(serializer.validated_data['amount']))
        user = self.request.user

        if (user.balance or Decimal('0.00')) < amount:
            raise serializers.ValidationError("Insufficient balance for this investment.")

        with transaction.atomic():
            user.balance = (user.balance or Decimal('0.00')) - amount
            if hasattr(user, 'total_invested'):
                user.total_invested = (user.total_invested or Decimal('0.00')) + amount
                user.save(update_fields=['balance', 'total_invested'])
            else:
                user.save(update_fields=['balance'])

            expected_return = amount + (
                amount * (Decimal(str(plan.daily_profit)) / Decimal('100.00')) * Decimal(str(plan.duration_days))
            )
            end_date = timezone.now() + timezone.timedelta(days=int(plan.duration_days))

            serializer.save(user=user, expected_return=expected_return, end_date=end_date)


class UserDepositCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            amount = Decimal(str(request.data.get('amount', 0)))
            gateway = request.data.get('gateway') or request.data.get('method', 'USDT TRC20')
            plan_id = request.data.get('plan_id')
        except (ValueError, TypeError):
            return Response({"error": "Invalid deposit amount."}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({"error": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        plan = None
        if plan_id:
            plan = InvestmentPlan.objects.filter(pk=plan_id).first()
            if plan:
                if amount < plan.min_deposit:
                    return Response(
                        {"error": f"Amount is below the minimum deposit of ${plan.min_deposit} for this plan."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if plan.max_deposit and amount > plan.max_deposit:
                    return Response(
                        {"error": f"Amount exceeds the maximum deposit of ${plan.max_deposit} for this plan."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        unique_tx_id = request.data.get('transaction_id') or f"TX-{uuid.uuid4().hex[:10].upper()}"

        with transaction.atomic():
            deposit = Deposit.objects.create(
                user=request.user,
                plan=plan,
                gateway=gateway,
                amount=amount,
                transaction_id=unique_tx_id,
                status='PENDING',
            )

            Transaction.objects.create(
                user=request.user,
                transaction_type='INVESTMENT' if plan else 'DEPOSIT',
                amount=amount,
                payment_method=gateway,
                transaction_id=unique_tx_id,
                status='PENDING',
            )

        send_admin_alert(
            title="💰 New Deposit Submitted",
            message=(
                f"User: {request.user.username}\n"
                f"Plan: {plan.name if plan else 'Direct Balance Deposit'}\n"
                f"Amount: ${amount:,.2f}\n"
                f"Gateway: {gateway}\n"
                f"Reference: {unique_tx_id}"
            ),
            priority="urgent",
            tags="moneybag",
        )

        send_user_email(
            to_email=request.user.email,
            subject=f"Deposit Request Submitted - {unique_tx_id}",
            message=(
                f"Hi {request.user.username},\n\n"
                f"We have received your deposit submission:\n"
                f"- Amount: ${amount:,.2f}\n"
                f"- Gateway: {gateway}\n"
                f"- Plan: {plan.name if plan else 'Account Balance'}\n"
                f"- Reference: {unique_tx_id}\n"
                f"- Status: PENDING\n\n"
                f"Your deposit will be credited once confirmed."
            ),
        )

        return Response(
            {
                "success": True,
                "message": f"Deposit request of ${amount:.2f} submitted! Awaiting admin confirmation.",
                "deposit_id": deposit.id,
                "transaction_id": unique_tx_id,
            },
            status=status.HTTP_201_CREATED,
        )


class UserWithdrawalCreateView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            amount = Decimal(str(request.data.get('amount', 0)))
            method = request.data.get('method') or request.data.get('gateway', 'USDT TRC20')
            wallet_address = request.data.get('wallet_address') or request.data.get('payout_address') or ''
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid withdrawal amount or data format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount <= 0:
            return Response({"error": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                user = request.user
                profile = getattr(user, 'profile', user)

                current_balance = Decimal(str(getattr(profile, 'balance', 0)))
                if current_balance < amount:
                    return Response({"error": "Insufficient balance for this withdrawal."}, status=status.HTTP_400_BAD_REQUEST)

                profile.balance = current_balance - amount
                profile.save()

                withdrawal = WithdrawalRequest.objects.create(
                    user=user,
                    amount=amount,
                    method=method,
                    status='PENDING',
                )

                Transaction.objects.create(
                    user=user,
                    transaction_type='WITHDRAWAL',
                    amount=amount,
                    payment_method=method,
                    status='PENDING',
                )

            send_admin_alert(
                title="🚨 New Withdrawal Request",
                message=(
                    f"User: {user.username}\n"
                    f"Amount: ${amount:,.2f}\n"
                    f"Method: {method}\n"
                    f"Wallet: {wallet_address or 'N/A'}\n"
                    f"Request ID: #{withdrawal.id}"
                ),
                priority="urgent",
                tags="rotating_light",
            )

            send_user_email(
                to_email=user.email,
                subject=f"Withdrawal Request Received (#{withdrawal.id})",
                message=(
                    f"Hi {user.username},\n\n"
                    f"Your withdrawal request has been submitted and is currently pending review:\n"
                    f"- Request ID: #{withdrawal.id}\n"
                    f"- Amount: ${amount:,.2f}\n"
                    f"- Method: {method}\n"
                    f"- Wallet: {wallet_address or 'N/A'}\n"
                    f"- Status: PENDING\n\n"
                    f"We will notify you once your withdrawal is processed."
                ),
            )

            return Response(
                {
                    "success": True,
                    "message": f"Withdrawal request of ${amount:.2f} submitted successfully!",
                    "withdrawal_id": withdrawal.id,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserTransactionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
        data = [
            {
                'id': tx.id,
                'type': tx.transaction_type,
                'amount': float(tx.amount),
                'status': tx.status,
                'method': tx.payment_method or 'USDT TRC20',
                'date': tx.created_at.strftime("%b-%d-%Y %I:%M %p") if tx.created_at else '',
            }
            for tx in transactions
        ]
        return Response(data, status=status.HTTP_200_OK)


class UserDepositsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')
        data = [
            {
                "id": d.id,
                "gateway": d.gateway,
                "amount": str(d.amount),
                "transaction_id": d.transaction_id,
                "status": d.status,
                "created_at": d.created_at.strftime('%Y-%m-%d %H:%M'),
            }
            for d in deposits
        ]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        gateway = request.data.get('gateway')
        amount = request.data.get('amount')
        transaction_id = request.data.get('transaction_id')
        plan_id = request.data.get('plan_id')

        if not gateway or not amount or not transaction_id:
            return Response(
                {"error": "All fields (gateway, amount, transaction_id) are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parsed_amount = Decimal(str(amount))
            if parsed_amount <= 0:
                return Response({"error": "Amount must be greater than zero."}, status=status.HTTP_400_BAD_REQUEST)

            plan = InvestmentPlan.objects.filter(pk=plan_id).first() if plan_id else None

            with transaction.atomic():
                deposit = Deposit.objects.create(
                    user=request.user,
                    plan=plan,
                    gateway=gateway,
                    amount=parsed_amount,
                    transaction_id=transaction_id,
                    status='PENDING',
                )

                Transaction.objects.create(
                    user=request.user,
                    transaction_type='INVESTMENT' if plan else 'DEPOSIT',
                    amount=parsed_amount,
                    payment_method=gateway,
                    transaction_id=transaction_id,
                    status='PENDING',
                )

            try:
                send_admin_alert(
                    title="💰 New Deposit Submitted",
                    message=(
                        f"User: {request.user.username}\n"
                        f"Plan: {plan.name if plan else 'Direct Balance Deposit'}\n"
                        f"Amount: ${parsed_amount:,.2f}\n"
                        f"Gateway: {gateway}\n"
                        f"Reference: {transaction_id}"
                    ),
                    priority="urgent",
                    tags="moneybag",
                )
            except Exception as alert_err:
                print(f"ADMIN ALERT ERROR: {alert_err}")

            send_user_email(
                to_email=request.user.email,
                subject=f"Deposit Submitted - Reference {transaction_id}",
                message=(
                    f"Hi {request.user.username},\n\n"
                    f"We have received your deposit submission:\n"
                    f"- Amount: ${parsed_amount:,.2f}\n"
                    f"- Gateway: {gateway}\n"
                    f"- Plan: {plan.name if plan else 'Account Balance'}\n"
                    f"- Reference: {transaction_id}\n"
                    f"- Status: PENDING\n\n"
                    f"Your deposit will be credited once confirmed."
                ),
            )

            return Response(
                {
                    "success": True,
                    "message": "Deposit submitted successfully! Waiting for admin approval.",
                    "deposit_id": deposit.id,
                },
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserWithdrawalsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        withdrawals = Withdrawal.objects.filter(user=request.user).order_by('-created_at')
        data = [
            {
                "id": w.id,
                "gateway": w.gateway,
                "amount": str(w.amount),
                "wallet_address": w.wallet_address,
                "status": w.status,
                "created_at": w.created_at.strftime('%Y-%m-%d %H:%M'),
            }
            for w in withdrawals
        ]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        gateway = request.data.get('gateway')
        wallet_address = request.data.get('wallet_address')

        try:
            amount = Decimal(str(request.data.get('amount', 0)))
        except (ValueError, TypeError):
            return Response({"error": "Invalid withdrawal amount."}, status=status.HTTP_400_BAD_REQUEST)

        if not gateway or amount <= 0 or not wallet_address:
            return Response(
                {"error": "Valid gateway, amount, and wallet address are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                user = request.user
                profile = getattr(user, 'profile', user)

                current_balance = Decimal(str(getattr(profile, 'balance', 0)))
                if current_balance < amount:
                    return Response({"error": "Insufficient balance for this withdrawal."}, status=status.HTTP_400_BAD_REQUEST)

                profile.balance = current_balance - amount
                profile.save()

                withdrawal = Withdrawal.objects.create(
                    user=user,
                    gateway=gateway,
                    amount=amount,
                    wallet_address=wallet_address,
                    status='PENDING',
                )

            send_admin_alert(
                title="🚨 New Withdrawal Request",
                message=(
                    f"User: {user.username}\n"
                    f"Amount: ${amount:,.2f}\n"
                    f"Gateway: {gateway}\n"
                    f"Wallet: {wallet_address}\n"
                    f"Request ID: #{withdrawal.id}"
                ),
                priority="urgent",
                tags="bank",
            )

            send_user_email(
                to_email=user.email,
                subject=f"Withdrawal Request Received (#{withdrawal.id})",
                message=(
                    f"Hi {user.username},\n\n"
                    f"Your withdrawal request has been submitted and is currently pending review:\n"
                    f"- Request ID: #{withdrawal.id}\n"
                    f"- Amount: ${amount:,.2f}\n"
                    f"- Gateway: {gateway}\n"
                    f"- Wallet Address: {wallet_address}\n"
                    f"- Status: PENDING\n\n"
                    f"We will notify you once your withdrawal is processed."
                ),
            )

            return Response(
                {
                    "success": True,
                    "message": "Withdrawal request submitted successfully!",
                    "id": withdrawal.id,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        referred_by_code = self.request.data.get('referred_by')
        print(f"--- PERFORM_CREATE TRIGGERED. REF ID: {referred_by_code} ---")

        with transaction.atomic():
            new_user = serializer.save()

            if referred_by_code:
                clean_ref = str(referred_by_code).strip()
                referrer = None

                if clean_ref.isdigit():
                    referrer = User.objects.filter(id=int(clean_ref)).first()

                print(f"--- REFERRER LOOKUP RESULT ---: {referrer}")

                if referrer and referrer != new_user:
                    new_user.referred_by = referrer
                    new_user.save(update_fields=['referred_by'])

                    referrer.balance = (referrer.balance or Decimal('0.00')) + INSTANT_SIGNUP_BONUS
                    referrer.referral_bonus_earned = (
                        getattr(referrer, 'referral_bonus_earned', Decimal('0.00')) or Decimal('0.00')
                    ) + INSTANT_SIGNUP_BONUS
                    referrer.save(update_fields=['balance', 'referral_bonus_earned'])

                    try:
                        Transaction.objects.create(
                            user=referrer,
                            transaction_type='EARNING',
                            amount=INSTANT_SIGNUP_BONUS,
                            status='APPROVED',
                        )
                        print(f"--- $5.00 BONUS SUCCESSFULLY CREDITED & LOGGED FOR ID {referrer.id} ---")
                    except Exception as tx_err:
                        print(f"--- WARNING: Bonus credited, but transaction log failed: {tx_err} ---")
                else:
                    print("--- WARNING: Referrer match failed or referrer is new_user ---")

        send_user_email(
            to_email=new_user.email,
            subject="Welcome to Grove Assets - Account Created",
            message=(
                f"Hi {new_user.username},\n\n"
                f"Welcome to Grove Assets! Your account has been created successfully.\n"
                f"You can now sign in to your dashboard to explore investment plans, make deposits, and manage your account.\n\n"
                f"If you did not register this account, please contact our support team immediately."
            ),
        )


class UserDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = request.user

        try:
            approved_deposits = Deposit.objects.filter(user=user, status='APPROVED')
            total_deposit = approved_deposits.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            all_investments = ActiveInvestment.objects.filter(user=user)
            for inv in all_investments:
                inv.check_and_update_expiry()

            active_investments_qs = ActiveInvestment.objects.filter(user=user, status='ACTIVE')
            active_investment_total = active_investments_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            total_earned = Decimal('0.00')
            for inv in all_investments:
                total_earned += inv.calculate_accumulated_profit() or Decimal('0.00')

            approved_withdrawals = Withdrawal.objects.filter(user=user, status='APPROVED')
            withdrew_total = approved_withdrawals.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

            user.refresh_from_db(fields=['balance'])
            balance = Decimal(str(getattr(user, 'balance', 0)))

            return Response(
                {
                    "username": user.username,
                    "deposited": float(total_deposit),
                    "total_deposit": float(total_deposit),
                    "active_investment": float(active_investment_total),
                    "active_investments": float(active_investment_total),
                    "earned": float(total_earned),
                    "total_earned": float(total_earned),
                    "withdrew_total": float(withdrew_total),
                    "balance": float(max(Decimal('0.00'), balance)),
                    "ref_bonus": float(getattr(user, 'referral_bonus_earned', 0.00) or 0.00),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class UserInvestPlanView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            plan_id = request.data.get('plan_id')
            amount = Decimal(str(request.data.get('amount', 0)))
            payment_method = str(request.data.get('payment_method', '')).strip()

            if amount <= 0:
                return Response({'error': 'Invalid investment amount.'}, status=status.HTTP_400_BAD_REQUEST)

            plan = InvestmentPlan.objects.filter(id=plan_id).first()
            if not plan:
                return Response({'error': 'Investment plan not found.'}, status=status.HTTP_404_NOT_FOUND)

            if amount < plan.min_deposit:
                return Response(
                    {'error': f'Amount is below the minimum deposit of ${plan.min_deposit} for this plan.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if plan.max_deposit and amount > plan.max_deposit:
                return Response(
                    {'error': f'Amount exceeds the maximum deposit of ${plan.max_deposit} for this plan.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if payment_method == 'Account Balance':
                with transaction.atomic():
                    user = User.objects.select_for_update().get(pk=request.user.pk)
                    current_balance = Decimal(str(getattr(user, 'balance', 0)))

                    if current_balance < amount:
                        return Response(
                            {'error': 'Insufficient account balance for this reinvestment.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    user.balance = current_balance - amount
                    user.save(update_fields=['balance'])

                    active_investment = ActiveInvestment.objects.create(
                        user=user,
                        plan=plan,
                        amount=amount,
                        daily_profit_percentage=plan.daily_profit,
                        duration_days=plan.duration_days,
                        status='ACTIVE',
                    )

                    Transaction.objects.create(
                        user=user,
                        transaction_type='REINVESTMENT',
                        amount=amount,
                        payment_method='Account Balance',
                        status='APPROVED',
                    )

                send_admin_alert(
                    title="⚡ Plan Reinvested (Balance)",
                    message=(
                        f"User: {request.user.username}\n"
                        f"Plan: {plan.name}\n"
                        f"Amount: ${amount:,.2f}\n"
                        f"Method: Account Balance"
                    ),
                    priority="default",
                    tags="zap",
                )

                return Response(
                    {
                        'success': True,
                        'message': 'Plan activated successfully!',
                        'active_investment_id': active_investment.id,
                        'new_balance': str(user.balance),
                    },
                    status=status.HTTP_201_CREATED,
                )

            unique_tx_id = f"TX-{uuid.uuid4().hex[:10].upper()}"
            gateway = payment_method or 'Crypto Deposit'

            Deposit.objects.create(
                user=request.user,
                plan=plan,
                gateway=gateway,
                amount=amount,
                transaction_id=unique_tx_id,
                status='PENDING',
            )

            Transaction.objects.create(
                user=request.user,
                transaction_type='INVESTMENT',
                amount=amount,
                payment_method=gateway,
                transaction_id=unique_tx_id,
                status='PENDING',
            )

            send_admin_alert(
                title="💰 New Deposit / Investment Order",
                message=(
                    f"User: {request.user.username}\n"
                    f"Plan: {plan.name}\n"
                    f"Amount: ${amount:,.2f}\n"
                    f"Gateway: {gateway}\n"
                    f"Reference: {unique_tx_id}"
                ),
                priority="urgent",
                tags="moneybag",
            )

            send_user_email(
                to_email=request.user.email,
                subject=f"Investment Order Created - {unique_tx_id}",
                message=(
                    f"Hi {request.user.username},\n\n"
                    f"Your investment order has been initialized:\n"
                    f"- Plan: {plan.name}\n"
                    f"- Amount: ${amount:,.2f}\n"
                    f"- Gateway: {gateway}\n"
                    f"- Reference: {unique_tx_id}\n"
                    f"- Status: PENDING\n\n"
                    f"Please complete your deposit so it can be confirmed."
                ),
            )

            return Response(
                {
                    'success': True,
                    'message': 'Investment order initialized. Please complete your deposit.',
                    'transaction_id': unique_tx_id,
                    'pending': True,
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import ProcessingGateway

class UserProcessingsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        gateways = ProcessingGateway.objects.filter(status='ON').order_by('id')
        data = [{
            "id": g.id,
            "name": g.name,
            "code": g.code,
            "status": g.status,
            "wallet_address": g.wallet_address or "",
            "instructions": g.instructions or "",
            "min_deposit": str(g.min_deposit),
            "max_deposit": str(g.max_deposit),
            "min_withdraw": str(g.min_withdraw),
            "max_withdraw": str(g.max_withdraw),
        } for g in gateways]
        return Response(data, status=status.HTTP_200_OK)