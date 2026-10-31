from rest_framework import serializers
from .models import InvestmentPlan, User, UserInvestment, Transaction, WithdrawalRequest
from django.db.models import Sum, Q

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




from rest_framework import serializers

# If you have an Admin User List serializer, include these fields:
class AdminUserDetailSerializer(serializers.ModelSerializer):
    total_deposit = serializers.SerializerMethodField()
    active_deposit = serializers.SerializerMethodField()

    class Meta:
        model = User  # or your custom user model
        fields = [
            'id', 'username', 'email', 'balance', 
            'total_deposit', 'active_deposit', 
            'btc_address', 'usdt_trc20', 'usdt_erc20', 'eth_address', 'bnb_address'
        ]

    def get_total_deposit(self, obj):
        # Sums all approved deposits
        return obj.deposits.filter(status='APPROVED').aggregate(Sum('amount'))['amount__sum'] or 0.00

    def get_active_deposit(self, obj):
        # Sums all pending/active deposits
        return obj.deposits.filter(status='PENDING').aggregate(Sum('amount'))['amount__sum'] or 0.00





class UserProfileSerializer(serializers.ModelSerializer):
    active_investments = serializers.SerializerMethodField()
    total_earned = serializers.SerializerMethodField()
    total_referrals = serializers.SerializerMethodField()
    referral_bonus_earned = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'balance', 
            'active_investments', 'total_earned', 
            'total_referrals', 'referral_bonus_earned',  # <--- ADDED HERE
            'btc_address', 'usdt_trc20', 'usdt_erc20', 'eth_address', 'bnb_address'
        ]

    def get_active_investments(self, obj):
        # Sums active user investments (adjust filter status based on your UserInvestment model)
        return obj.userinvestments.filter(is_completed=False).aggregate(Sum('amount'))['amount__sum'] or 0.00

    def get_total_earned(self, obj):
        # Sums completed profits or earnings from transactions
        return obj.transactions.filter(type='PROFIT', status='APPROVED').aggregate(Sum('amount'))['amount__sum'] or 0.00

    def get_total_referrals(self, obj):
        return obj.referrals.count()



class WithdrawalRequestSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    wallet_address = serializers.SerializerMethodField()
    transaction_id = serializers.SerializerMethodField() # Or direct field if it exists on the model

    class Meta:
        model = WithdrawalRequest
        fields = [
            'id', 'user', 'username', 'user_email', 'amount', 
            'method', 'wallet_address', 'transaction_id', 'status', 'created_at'
        ]
        read_only_fields = ['user', 'created_at']

    def get_wallet_address(self, obj):
        user = obj.user
        for field in ['usdt_trc20', 'wallet_address', 'usdt_address', 'payout_address']:
            if hasattr(user, field):
                val = getattr(user, field)
                if val:
                    return val
        return 'N/A'

    def get_transaction_id(self, obj):
        # Check common field names for transaction hashes/references on the model
        for field in ['transaction_id', 'tx_hash', 'reference', 'hash']:
            if hasattr(obj, field):
                val = getattr(obj, field)
                if val:
                    return val
        return 'N/A'