from django.db import models
from django.conf import settings

class InvestmentPlan(models.Model):
    name = models.CharField(max_length=100)
    min_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    max_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    daily_profit = models.DecimalField(max_digits=5, decimal_places=2)
    duration_days = models.IntegerField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.daily_profit}% daily)"


class UserInvestment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='investments')
    plan = models.ForeignKey(InvestmentPlan, on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    expected_return = models.DecimalField(max_digits=12, decimal_places=2)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    is_completed = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} - ${self.amount}"


class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('DEPOSIT', 'Deposit'),
        ('WITHDRAWAL', 'Withdrawal'),
        ('EARNING', 'Earning'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.transaction_type}: ${self.amount} [{self.status}]"


from django.db import get_user_model, models
from decimal import Decimal

User = get_user_model()

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('deposit', 'Deposit'),
        ('withdrawal', 'Withdrawal'),
        ('credit', 'Admin Credit'),
        ('earning', 'Daily Earning'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    package_name = models.CharField(max_length=100, blank=True, null=True)
    payment_method = models.CharField(max_length=50, blank=True, null=True)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.type} - ${self.amount}"

class WithdrawalRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='withdrawals')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=50, default='USDT TRC20')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Withdrawal #{self.id} - {self.user.username} - ${self.amount}"

class SystemSetting(models.Model):
    platform_name = models.CharField(max_length=100, default='Crystals Investments')
    
    def __str__(self):
        return self.platform_name