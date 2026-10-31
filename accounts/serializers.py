from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

class UserSerializer(serializers.ModelSerializer):
    total_referrals = serializers.SerializerMethodField()
    referral_bonus_earned = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'balance', 'total_invested', 'total_earned', 'is_staff', 'is_superuser', 'is_blacklisted', 'total_referrals', 'referral_bonus_earned']


    def get_total_referrals(self, obj):
        return obj.referrals.count()

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