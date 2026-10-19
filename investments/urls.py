from django.urls import path
from .admin_views import (
    AdminUserListView,
    AdminUserDetailView,
    AdminCreditUserBalanceView,
    AdminTransactionListView,
    AdminWithdrawalListView,
    AdminProcessWithdrawalView,
    AdminSystemSettingsView,
    AdminProcessingsView
)
from .views import (
    InvestmentPlanListView,
    UserDepositCreateView,
    UserWithdrawalCreateView,
    UserTransactionListView
)

urlpatterns = [
    # User-facing endpoints
    path('plans/', InvestmentPlanListView.as_view(), name='investment-plans'),
    path('deposit/', UserDepositCreateView.as_view(), name='user-deposit'),
    path('withdraw/', UserWithdrawalCreateView.as_view(), name='user-withdraw'),
    path('transactions/', UserTransactionListView.as_view(), name='user-transactions'),

    # Admin endpoints
    path('admin/users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/credit-user/', AdminCreditUserBalanceView.as_view(), name='admin-credit-user'),
    path('admin/transactions/', AdminTransactionListView.as_view(), name='admin-transactions'),
    path('admin/withdrawals/pending/', AdminWithdrawalListView.as_view(), name='admin-withdrawals'),
    path('admin/withdrawals/<int:pk>/process/', AdminProcessWithdrawalView.as_view(), name='admin-process-withdrawal'),
    path('admin/settings/', AdminSystemSettingsView.as_view(), name='admin-system-settings'),

    path('admin/processings/', AdminProcessingsView.as_view(), name='admin-processings'),
    path('admin/processings/<int:pk>/', AdminProcessingsView.as_view(), name='admin-processing-detail'),
]