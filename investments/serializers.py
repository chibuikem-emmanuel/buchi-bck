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



