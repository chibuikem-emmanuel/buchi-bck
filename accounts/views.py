from rest_framework import generics, permissions
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from investments.models import Transaction

from .serializers import CustomTokenObtainPairSerializer, RegisterSerializer, UserSerializer

User = get_user_model()

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# class RegisterView(generics.CreateAPIView):
#     queryset = User.objects.all()
#     serializer_class = RegisterSerializer
#     permission_classes = [permissions.AllowAny]

class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
    








User = get_user_model()

# Define the instant referral bonus amount
INSTANT_SIGNUP_BONUS = Decimal('5.00')

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]  # Fixed typo here

    def perform_create(self, serializer):
        referred_by_code = self.request.data.get('referred_by')
        print(f"--- PERFORM_CREATE TRIGGERED. REF CODE: {referred_by_code} ---")

        with transaction.atomic():
            # 1. Save the new user using the DRF serializer
            new_user = serializer.save()

            # 2. Process instant referral bonus if ref code was provided
            if referred_by_code:
                clean_ref = referred_by_code.strip()
                
                # Find the referrer case-insensitively by email or username
                referrer = User.objects.filter(
                    Q(email__iexact=clean_ref) | Q(username__iexact=clean_ref)
                ).first()

                print(f"--- REFERRER LOOKUP RESULT ---: {referrer}")

                if referrer and referrer != new_user:
                    # Link the referral relationship
                    new_user.referred_by = referrer
                    new_user.save(update_fields=['referred_by'])

                    # Credit the referrer's balance and total referral commission earned
                    referrer.balance += INSTANT_SIGNUP_BONUS
                    referrer.referral_bonus_earned += INSTANT_SIGNUP_BONUS
                    referrer.save(update_fields=['balance', 'referral_bonus_earned'])

                    # Safely create transaction record using valid model fields
                    try:
                        Transaction.objects.create(
                            user=referrer,
                            amount=INSTANT_SIGNUP_BONUS,
                            status='APPROVED'
                        )
                        print(f"--- $5.00 BONUS SUCCESSFULLY CREDITED & LOGGED FOR {referrer.email} ---")
                    except Exception as tx_err:
                        print(f"--- WARNING: Bonus credited, but transaction log failed: {tx_err} ---")
                else:
                    print("--- WARNING: Referrer match failed or referrer is new_user ---")





