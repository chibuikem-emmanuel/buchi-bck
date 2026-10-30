from rest_framework import generics, permissions
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.db import transaction
from .models import Transaction
from .serializers import CustomTokenObtainPairSerializer, RegisterSerializer, UserSerializer

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user





INSTANT_SIGNUP_BONUS = Decimal('5.00')

class RegisterView(APIView):
    def post(self, request):
        data = request.data
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        phone_number = data.get('phone_number')
        country = data.get('country')
        payout_address = data.get('payout_address')
        referred_by_code = data.get('referred_by')

        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username already taken'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)

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
                # Find the referrer by username or email
                referrer = User.objects.filter(username__iexact=referred_by_code).first() or \
                           User.objects.filter(email__iexact=referred_by_code).first()

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
                        description=f'Instant referral bonus for user registration: {new_user.username}'
                    )

        return Response({'message': 'Registration successful!'}, status=status.HTTP_201_CREATED)