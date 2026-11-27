from django.db import models, transaction
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

    def __str__(self):
        return f"{self.user.username} - ${self.amount} ({self.status})"

    def save(self, *args, **kwargs):
        # Pure database save. No balance modification here.
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
    wallet_address = models.CharField(max_length=255, blank=True, null=True, default='')
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






def _normalize_dt(dt):
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


class ActiveInvestment(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'ACTIVE'),
        ('COMPLETED', 'COMPLETED'),
        ('CANCELLED', 'CANCELLED'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='active_investments'
    )
    plan = models.ForeignKey('InvestmentPlan', on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    daily_profit_percentage = models.DecimalField(max_digits=5, decimal_places=2, default='4.00')
    duration_days = models.IntegerField(default=3)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - ${self.amount} ({self.status})"

    def calculate_accumulated_profit(self):
        start_dt = _normalize_dt(self.start_date)
        if not start_dt:
            return Decimal('0.00')

        now = timezone.now()
        end_dt = _normalize_dt(self.end_date)
        effective_end = min(now, end_dt) if end_dt else now
        if effective_end <= start_dt:
            return Decimal('0.00')

        total_seconds = Decimal(str((effective_end - start_dt).total_seconds()))
        days_elapsed = min(
            total_seconds / Decimal('86400'),
            Decimal(str(max(self.duration_days or 0, 0)))
        )

        amt = Decimal(str(self.amount or '0.00'))
        pct = Decimal(str(self.daily_profit_percentage or '0.00'))
        daily_profit = amt * (pct / Decimal('100.00'))
        return (daily_profit * days_elapsed).quantize(Decimal('0.01'))

    def check_and_update_expiry(self):
        end_dt = _normalize_dt(self.end_date)
        if self.status == 'ACTIVE' and not self.is_completed and end_dt:
            if timezone.now() >= end_dt:
                with transaction.atomic():
                    inv = ActiveInvestment.objects.select_for_update().select_related('user').get(pk=self.pk)
                    inv_end = _normalize_dt(inv.end_date)
                    if (
                        inv.status == 'ACTIVE'
                        and not inv.is_completed
                        and inv_end
                        and timezone.now() >= inv_end
                    ):
                        locked_user = User.objects.select_for_update().get(pk=inv.user_id)
                        release_amount = Decimal(str(inv.amount or '0.00'))

                        inv.status = 'COMPLETED'
                        inv.is_completed = True
                        inv.save(update_fields=['status', 'is_completed'])

                        locked_user.balance = Decimal(str(locked_user.balance or '0.00')) + release_amount
                        locked_user.save(update_fields=['balance'])

                        Transaction.objects.create(
                            user=locked_user,
                            transaction_type='PRINCIPAL_RELEASE',
                            amount=release_amount,
                            status='APPROVED',
                            transaction_id=f"REL-{inv.id}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
                        )
                        self.refresh_from_db()

    def save(self, *args, **kwargs):
        if not self.start_date:
            self.start_date = timezone.now()
        if not self.end_date:
            days = int(self.duration_days if self.duration_days is not None else 3)
            start_dt = _normalize_dt(self.start_date)
            self.end_date = start_dt + timedelta(days=days)
        super().save(*args, **kwargs)


