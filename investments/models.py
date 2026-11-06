from django.db import models
from django.contrib.auth import get_user_model
from decimal import Decimal
from django.conf import settings
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta




User = get_user_model()







class InvestmentPlan(models.Model):
    name = models.CharField(max_length=100)
    min_deposit = models.DecimalField(max_digits=12, decimal_places=2, default='100.00')
    max_deposit = models.DecimalField(max_digits=12, decimal_places=2, default='10000.00')
    daily_profit = models.DecimalField(max_digits=5, decimal_places=2, help_text="Daily profit percentage e.g. 4.00 for 4%")
    duration_days = models.IntegerField(default=3)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.daily_profit}% daily for {self.duration_days} days)"


class UserInvestment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='investments')
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default='0.00')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.amount}"


class Transaction(models.Model):
    TRANSACTION_TYPE = (
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('INVESTMENT', 'Investment Plan Deposit'),
        ('EARNING', 'Daily Earning'),
        ('PRINCIPAL_RELEASE', 'Principal Release'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPE, default='DEPOSIT')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default='0.00')
    payment_method = models.CharField(max_length=100, blank=True, null=True, default='USDT TRC20')
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.transaction_type} (${self.amount})"


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
        ('APPROVED', 'APPROVED'),
        ('REJECTED', 'REJECTED'),
    )
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='deposits')
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='deposits')
    gateway = models.CharField(max_length=100, default='USDT TRC20')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Check if this is an update transitioning from PENDING to APPROVED
        if self.pk:
            old_instance = Deposit.objects.filter(pk=self.pk).first()
            if old_instance and old_instance.status != 'APPROVED' and self.status == 'APPROVED':
                
                if self.plan is not None:
                    # 1. Plan-based deposit: Lock capital into ActiveInvestment. Balance is NOT touched.
                    ActiveInvestment.objects.create(
                        user=self.user,
                        plan=self.plan,
                        amount=self.amount,
                        daily_profit_percentage=self.plan.daily_profit,
                        duration_days=self.plan.duration_days,
                        status='ACTIVE'
                    )
                    Transaction.objects.create(
                        user=self.user,
                        transaction_type='INVESTMENT',
                        amount=self.amount,
                        status='APPROVED',
                        transaction_id=f"INV-{self.transaction_id or self.id}"
                    )
                else:
                    # 2. General wallet deposit (no plan): Funds spendable balance directly.
                    self.user.balance += self.amount
                    self.user.save()

                    Transaction.objects.create(
                        user=self.user,
                        transaction_type='DEPOSIT',
                        amount=self.amount,
                        status='APPROVED',
                        transaction_id=f"DEP-{self.transaction_id or self.id}"
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
        ('ACTIVE', 'ACTIVE'),
        ('COMPLETED', 'COMPLETED'),
        ('CANCELLED', 'CANCELLED'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='active_investments')
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    daily_profit_percentage = models.DecimalField(max_digits=5, decimal_places=2, default='4.00')
    duration_days = models.IntegerField(default=3)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - ${self.amount} ({self.status})"

    def calculate_accumulated_profit(self):
        """Calculates real-time daily earnings based on 24-hour cycles elapsed, capped at plan duration."""
        if not self.start_date:
            return Decimal('0.00')
        
        delta = timezone.now() - self.start_date
        days_elapsed = min(Decimal(str(delta.total_seconds())) / Decimal('86400'), Decimal(str(self.duration_days)))
        if days_elapsed < 0:
            days_elapsed = Decimal('0.00')

        daily_profit = self.amount * (self.daily_profit_percentage / Decimal('100.00'))
        return (daily_profit * days_elapsed).quantize(Decimal('0.01'))

    def check_and_update_expiry(self):
        """Expires the investment once duration passes and releases principal back to spendable balance."""
        if self.status == 'ACTIVE' and not self.is_completed:
            if self.end_date and timezone.now() >= self.end_date:
                self.status = 'COMPLETED'
                self.is_completed = True
                self.save()

                # Release principal back to user balance exactly once upon expiry
                if self.user and self.amount:
                    self.user.balance += self.amount
                    self.user.save()

                Transaction.objects.create(
                    user=self.user,
                    transaction_type='PRINCIPAL_RELEASE',
                    amount=self.amount,
                    status='APPROVED'
                )

    def save(self, *args, **kwargs):
        if not self.end_date and self.start_date:
            self.end_date = self.start_date + timedelta(days=self.duration_days)
        super().save(*args, **kwargs)