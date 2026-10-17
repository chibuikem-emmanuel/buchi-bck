# investments/urls.py
from django.urls import path
from .views import InvestmentPlanListView, UserInvestmentCreateView, TransactionListCreateView
from .admin_views import (
    AdminSystemSettingsView,
    AdminUserListView,
    AdminUserDetailView,
    AdminTransactionListView,
    AdminWithdrawalListView,
    AdminProcessWithdrawalView,
    AdminCreditUserBalanceView,
    AdminInvestmentPlanCreateUpdateView,
)

from django.urls import path
from .views import InvestmentPlanListView, UserDepositCreateView, UserWithdrawalCreateView
from .admin_views import (
    AdminUserListView,
    AdminUserDetailView,
    AdminTransactionListView,
    AdminWithdrawalListView,
    AdminProcessWithdrawalView,
    AdminCreditUserBalanceView,
    AdminInvestmentPlanCreateUpdateView,
)

urlpatterns = [
    # User Endpoints
    path('plans/', InvestmentPlanListView.as_view(), name='investment-plans'),
    path('create/', UserInvestmentCreateView.as_view(), name='create-investment'),
    path('transactions/', TransactionListCreateView.as_view(), name='transactions'),


        # User Endpoints
    path('plans/', InvestmentPlanListView.as_view(), name='investment-plans'),
    path('deposits/', UserDepositCreateView.as_view(), name='user-deposit'),
    path('withdrawals/', UserWithdrawalCreateView.as_view(), name='user-withdrawal'),

    # Admin Management Endpoints
    path('admin/users/', AdminUserListView.as_view(), name='admin-users'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/credit-user/', AdminCreditUserBalanceView.as_view(), name='admin-credit-user'),
    path('admin/plans/manage/', AdminInvestmentPlanCreateUpdateView.as_view(), name='admin-manage-plans'),
    path('admin/transactions/', AdminTransactionListView.as_view(), name='admin-transactions'),
    path('admin/withdrawals/', AdminWithdrawalListView.as_view(), name='admin-withdrawals'),
    path('admin/withdrawals/<int:pk>/', AdminProcessWithdrawalView.as_view(), name='admin-process-withdrawal'),



    
    # Admin Management Endpoints
    path('admin/users/', AdminUserListView.as_view(), name='admin-users'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/credit-user/', AdminCreditUserBalanceView.as_view(), name='admin-credit-user'),
    path('admin/plans/manage/', AdminInvestmentPlanCreateUpdateView.as_view(), name='admin-manage-plans'),
    path('admin/transactions/', AdminTransactionListView.as_view(), name='admin-transactions'),
    path('admin/withdrawals/', AdminWithdrawalListView.as_view(), name='admin-withdrawals'),
    path('admin/withdrawals/<int:pk>/', AdminProcessWithdrawalView.as_view(), name='admin-process-withdrawal'),
    path('admin/settings/', AdminSystemSettingsView.as_view(), name='admin-settings')
]


# investments/urls.py


