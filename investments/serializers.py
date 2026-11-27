from django.db.models import Sum
from rest_framework import serializers
from .models import (
    ActiveInvestment,
    InvestmentPlan,
    ProcessingGateway,
    Transaction,
    User,
    UserInvestment,
    WithdrawalRequest,
)


class InvestmentPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentPlan
        fields = '__all__'


class UserInvestmentSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source='plan.name', read_only=True)

    class Meta:
        model = UserInvestment
        fields = '__all__'
        read_only_fields = ('user', 'expected_return', 'is_completed', 'end_date')


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'
        read_only_fields = ('user', 'status', 'created_at')


class AdminUserDetailSerializer(serializers.ModelSerializer):
    total_deposit = serializers.SerializerMethodField()
    active_deposit = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'balance',
            'total_deposit', 'active_deposit',
            'btc_address', 'usdt_trc20', 'usdt_erc20', 'eth_address', 'bnb_address',
        ]

    def get_total_deposit(self, obj):
        total = obj.deposits.filter(status='APPROVED').aggregate(Sum('amount'))['amount__sum']
        return float(total or 0.00)

    def get_active_deposit(self, obj):
        total = obj.deposits.filter(status='PENDING').aggregate(Sum('amount'))['amount__sum']
        return float(total or 0.00)


class UserProfileSerializer(serializers.ModelSerializer):
    deposited = serializers.SerializerMethodField()
    total_deposit = serializers.SerializerMethodField()
    active_investment = serializers.SerializerMethodField()
    total_earned = serializers.SerializerMethodField()
    withdrew_total = serializers.SerializerMethodField()
    total_referrals = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    investments = serializers.SerializerMethodField()
    referral_bonus_earned = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, default=0.00
    )

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'balance',
            'deposited', 'total_deposit', 'active_investment',
            'total_earned', 'withdrew_total',
            'total_referrals', 'referral_bonus_earned',
            'btc_address', 'usdt_trc20', 'usdt_erc20', 'eth_address', 'bnb_address',
            'investments',
        ]

    def _get_investments_queryset(self, obj):
        if hasattr(obj, 'active_investments'):
            return obj.active_investments.select_related('plan').order_by('-start_date')
        return ActiveInvestment.objects.filter(user=obj).select_related('plan').order_by('-start_date')

    def _process_user_expiries(self, obj):
        qs = self._get_investments_queryset(obj)
        for inv in qs.filter(status='ACTIVE', is_completed=False):
            if hasattr(inv, 'check_and_update_expiry'):
                inv.check_and_update_expiry()

    def get_deposited(self, obj):
        total = obj.deposits.filter(status='APPROVED').aggregate(Sum('amount'))['amount__sum']
        return float(total or 0.00)

    def get_total_deposit(self, obj):
        return self.get_deposited(obj)

    def get_active_investment(self, obj):
        self._process_user_expiries(obj)
        total = self._get_investments_queryset(obj).filter(status='ACTIVE').aggregate(Sum('amount'))['amount__sum']
        return float(total or 0.00)

    def get_total_earned(self, obj):
        self._process_user_expiries(obj)
        earned = 0.00
        for inv in self._get_investments_queryset(obj).filter(status__in=['ACTIVE', 'COMPLETED']):
            if hasattr(inv, 'calculate_accumulated_profit'):
                profit = inv.calculate_accumulated_profit()
                earned += float(profit or 0.00)
        return float(earned)

    def get_withdrew_total(self, obj):
        total = obj.withdrawals.filter(status='APPROVED').aggregate(Sum('amount'))['amount__sum']
        return float(total or 0.00)

    def get_total_referrals(self, obj):
        return obj.referrals.count() if hasattr(obj, 'referrals') else 0

    def get_balance(self, obj):
        return float(getattr(obj, 'balance', 0.00))

    def get_investments(self, obj):
        self._process_user_expiries(obj)
        items = []
        for inv in self._get_investments_queryset(obj):
            items.append({
                'id': inv.id,
                'plan_name': inv.plan.name if inv.plan else 'Investment Plan',
                'amount': float(inv.amount or 0.00),
                'daily_profit_percentage': float(inv.daily_profit_percentage or 0.00),
                'duration_days': inv.duration_days,
                'status': inv.status,
                'is_completed': inv.is_completed,
                'start_date': inv.start_date.isoformat() if inv.start_date else None,
                'end_date': inv.end_date.isoformat() if inv.end_date else None,
            })
        return items


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    wallet_address = serializers.SerializerMethodField()
    transaction_id = serializers.SerializerMethodField()

    class Meta:
        model = WithdrawalRequest
        fields = [
            'id', 'user', 'username', 'user_email', 'amount',
            'method', 'wallet_address', 'transaction_id', 'status', 'created_at',
        ]
        read_only_fields = ['user', 'created_at']

    def get_wallet_address(self, obj):
        user = obj.user
        for field in ['usdt_trc20', 'wallet_address', 'usdt_address', 'payout_address']:
            val = getattr(user, field, None)
            if val:
                return val
        return 'N/A'

    def get_transaction_id(self, obj):
        for field in ['transaction_id', 'tx_hash', 'reference', 'hash']:
            val = getattr(obj, field, None)
            if val:
                return val
        return 'N/A'


class ProcessingGatewaySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProcessingGateway
        fields = [
            'id',
            'name',
            'code',
            'status',
            'wallet_address',
            'instructions',
            'min_deposit',
            'max_deposit',
            'min_withdraw',
            'max_withdraw',
        ]