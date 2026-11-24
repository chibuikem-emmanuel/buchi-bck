from decimal import Decimal
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from crystals_core.notifications import send_user_email
from investments.models import Transaction
from .serializers import (
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserSerializer,
)

User = get_user_model()

# Define the instant referral bonus amount
INSTANT_SIGNUP_BONUS = Decimal('5.00')


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class UserProfileView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        referred_by_code = self.request.data.get('referred_by')
        print(f"--- PERFORM_CREATE TRIGGERED. REF ID: {referred_by_code} ---")

        with transaction.atomic():
            # 1. Save the new user using the DRF serializer
            new_user = serializer.save()

            # 2. Process instant referral bonus if ref ID was provided
            if referred_by_code:
                clean_ref = str(referred_by_code).strip()
                referrer = None

                # Check if the code is a valid number (User ID)
                if clean_ref.isdigit():
                    referrer = User.objects.filter(id=int(clean_ref)).first()

                print(f"--- REFERRER LOOKUP RESULT ---: {referrer}")

                if referrer and referrer != new_user:
                    # Link the referral relationship
                    new_user.referred_by = referrer
                    new_user.save(update_fields=['referred_by'])

                    # Credit the referrer's balance and total referral commission earned
                    referrer.balance = (referrer.balance or Decimal('0.00')) + INSTANT_SIGNUP_BONUS
                    referrer.referral_bonus_earned = (
                        getattr(referrer, 'referral_bonus_earned', Decimal('0.00')) or Decimal('0.00')
                    ) + INSTANT_SIGNUP_BONUS
                    referrer.save(update_fields=['balance', 'referral_bonus_earned'])

                    # Safely create transaction record using valid model fields
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
                f"You can now sign in to your dashboard to view investment plans, make deposits, and track your account.\n\n"
                f"If you did not create this account, please contact support immediately."
            ),
        )