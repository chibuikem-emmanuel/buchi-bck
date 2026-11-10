from django.db.models.aggregates import Sum
from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

class UserSerializer(serializers.ModelSerializer):
    deposited = serializers.SerializerMethodField()
    total_deposit = serializers.SerializerMethodField()
    active_investment = serializers.SerializerMethodField()
    total_earned = serializers.SerializerMethodField()
    withdrew_total = serializers.SerializerMethodField()
    total_referrals = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    referral_bonus_earned = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, default=0.00)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'phone_number', 'balance', 
            'total_invested', 'total_earned', 'is_staff', 'is_superuser', 
            'is_blacklisted', 'deposited', 'total_deposit', 'active_investment', 
            'withdrew_total', 'total_referrals', 'referral_bonus_earned',
            'btc_address', 'usdt_trc20', 'usdt_erc20', 'eth_address', 'bnb_address'
        ]

    def _process_user_expiries(self, obj):
        """On-demand lazy expiry check whenever user metrics are requested."""
        active_invs = getattr(obj, 'active_investments', None)
        if active_invs:
            for inv in active_invs.filter(status='ACTIVE', is_completed=False):
                if hasattr(inv, 'check_and_update_expiry'):
                    inv.check_and_update_expiry()

    def get_deposited(self, obj):
        total = obj.deposits.filter(status='APPROVED').aggregate(Sum('amount'))['amount__sum']
        return float(total or 0.00)

    def get_total_deposit(self, obj):
        return self.get_deposited(obj)

    def get_active_investment(self, obj):
        self._process_user_expiries(obj)
        investments = getattr(obj, 'active_investments', None)
        if investments:
            total = investments.filter(status='ACTIVE').aggregate(Sum('amount'))['amount__sum']
            return float(total or 0.00)
        return 0.00

    def get_total_earned(self, obj):
        investments = getattr(obj, 'active_investments', None)
        earned = 0.00
        if investments:
            for inv in investments.filter(status='ACTIVE'):
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


class UserProfileSerializer(serializers.ModelSerializer):
    deposited = serializers.SerializerMethodField()
    total_deposit = serializers.SerializerMethodField()
    active_investment = serializers.SerializerMethodField()
    total_earned = serializers.SerializerMethodField()
    withdrew_total = serializers.SerializerMethodField()
    total_referrals = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()
    referral_bonus_earned = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True, default=0.00)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'balance', 
            'deposited', 'total_deposit', 'active_investment', 
            'total_earned', 'withdrew_total',
            'total_referrals', 'referral_bonus_earned',
            'btc_address', 'usdt_trc20', 'usdt_erc20', 'eth_address', 'bnb_address'
        ]

    def _process_user_expiries(self, obj):
        """On-demand lazy expiry check whenever user metrics are requested."""
        active_invs = getattr(obj, 'active_investments', None)
        if active_invs:
            for inv in active_invs.filter(status='ACTIVE', is_completed=False):
                if hasattr(inv, 'check_and_update_expiry'):
                    inv.check_and_update_expiry()

    def get_deposited(self, obj):
        total = obj.deposits.filter(status='APPROVED').aggregate(Sum('amount'))['amount__sum']
        return float(total or 0.00)

    def get_total_deposit(self, obj):
        return self.get_deposited(obj)

    def get_active_investment(self, obj):
        self._process_user_expiries(obj)
        investments = getattr(obj, 'active_investments', None)
        if investments:
            total = investments.filter(status='ACTIVE').aggregate(Sum('amount'))['amount__sum']
            return float(total or 0.00)
        return 0.00

    def get_total_earned(self, obj):
        investments = getattr(obj, 'active_investments', None)
        earned = 0.00
        if investments:
            for inv in investments.filter(status='ACTIVE'):
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

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'phone_number']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data.get('username'),
            email=validated_data.get('email'),
            password=validated_data.get('password'),
            phone_number=validated_data.get('phone_number', '')
        )
        return user