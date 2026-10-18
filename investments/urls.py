from django.urls import path
from .admin_views import (
    AdminUserListView, 
    AdminUserDetailView, 
    AdminCreditUserBalanceView, 
    AdminTransactionListView, 
    AdminWithdrawalListView, 
    AdminProcessWithdrawalView
)

urlpatterns = [
    path('admin/users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/credit-user/', AdminCreditUserBalanceView.as_view(), name='admin-credit-user'),
    path('admin/transactions/', AdminTransactionListView.as_view(), name='admin-transactions'),
    path('admin/withdrawals/pending/', AdminWithdrawalListView.as_view(), name='admin-withdrawals'),
    path('admin/withdrawals/<int:pk>/process/', AdminProcessWithdrawalView.as_view(), name='admin-process-withdrawal'),
]