from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone




User = get_user_model()







class InvestmentPlan(models.Model):
    name = models.CharField(max_length=100)
    min_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('100.00'))
    max_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('4999.00'))
    daily_profit = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage e.g. 4.00 for 4%")
    duration_days = models.IntegerField(default=5)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.daily_profit}% daily)"


class UserInvestment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='investments')
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expected_return = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(blank=True, null=True)
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.amount} on {self.plan}"


class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('CREDIT', 'Admin Credit'),
        ('EARNING', 'Daily Earning'),
    )
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES, default='DEPOSIT')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    package_name = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True, default='USDT TRC20')
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} | {self.transaction_type} | ${self.amount}"


class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=50, default='USDT TRC20')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Withdrawal #{self.id} - {self.user.username} - ${self.amount}"



class Deposit(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deposits')
    plan = models.ForeignKey('InvestmentPlan', on_delete=models.SET_NULL, null=True, blank=True, related_name='deposits')
    gateway = models.CharField(max_length=100)  # e.g., "USDT TRC20" or "Account Balance"
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Check if an existing deposit is being updated to 'APPROVED' by admin
        if self.pk:
            old_instance = Deposit.objects.filter(pk=self.pk).first()
            if old_instance and old_instance.status != 'APPROVED' and self.status == 'APPROVED':
                
                if self.plan:
                    # 1. If a plan is attached, lock capital into an ActiveInvestment
                    ActiveInvestment.objects.create(
                        user=self.user,
                        plan=self.plan,
                        amount=self.amount,
                        daily_profit_percentage=getattr(self.plan, 'daily_profit_percentage', 4.00),
                        duration_days=getattr(self.plan, 'duration_days', 3),
                        status='ACTIVE'
                    )
                    
                    # Log transaction
                    Transaction.objects.create(
                        user=self.user,
                        transaction_type='INVESTMENT',
                        amount=self.amount,
                        status='APPROVED'
                    )
                else:
                    # 2. General wallet funding with no plan -> credit user balance
                    self.user.balance += self.amount
                    self.user.save()

                    Transaction.objects.create(
                        user=self.user,
                        transaction_type='DEPOSIT',
                        amount=self.amount,
                        status='APPROVED'
                    )

        super().save(*args, **kwargs)




class SystemSetting(models.Model):
    platform_name = models.CharField(max_length=100, default='GROVE ASSETS LTD')

    def save(self, *args, **kwargs):
        # Force the ID to always be 1 (Singleton pattern)
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'platform_name': 'GROVE ASSETS LTD'})
        return obj

    def __str__(self):
        return self.platform_name





class ProcessingGateway(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=10, default="ON")  # "ON" or "OFF"
    instructions = models.TextField(blank=True, null=True)
    min_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    max_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    min_withdraw = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    max_withdraw = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.name} ({self.code})"
    



class Withdrawal(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='platform_withdrawals')
    gateway = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    wallet_address = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']






class ActiveInvestment(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active'),
        ('EXPIRED', 'Expired'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='active_investments')
    plan = models.ForeignKey('InvestmentPlan', on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    daily_profit_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=4.00)
    duration_days = models.IntegerField(default=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True)

    def check_and_update_expiry(self):
        """Automatically expires the investment and returns principal to user balance once duration passes (runs strictly once)."""
        if self.status == 'ACTIVE':
            delta = timezone.now() - self.created_at
            if delta.days >= self.duration_days:
                self.status = 'EXPIRED'
                self.save()
                
                # Release principal back to spendable user balance exactly once upon expiration
                if self.user and self.amount:
                    self.user.balance += self.amount
                    self.user.save()
                    
        return self.status

    def calculate_accumulated_profit(self):
        """Calculates total profit earned so far for analytics (capped at plan duration)."""
        delta = timezone.now() - self.created_at
        days_elapsed = min(delta.days, self.duration_days)
        
        daily_profit = float(self.amount) * (float(self.daily_profit_percentage) / 100.0)
        return round(daily_profit * days_elapsed, 2)