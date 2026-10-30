from rest_framework import serializers
from .models import InvestmentPlan, User, UserInvestment, Transaction
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

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'balance', 
            'active_investments', 'total_earned', 
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