from rest_framework import serializers
from .models import InvestmentPlan, UserInvestment, Transaction

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