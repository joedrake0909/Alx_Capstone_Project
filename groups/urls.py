from django.urls import path
from . import views

urlpatterns = [
    # 1. The Entry Point & Redirector
    path('login-success/', views.login_success, name='login_success'),

    # 2. Master Admin Views (Superuser Dashboard)
    path('dashboard/', views.SuperuserDashboardView.as_view(), name='super_dashboard'),
    path('admins/', views.AdminUserListView.as_view(), name='admin_user_list'),
    path('transactions/all/', views.AllTransactionsView.as_view(), name='all_transactions'),
    
    # 3. Existing Member Management (Group Admin/Treasurer views)
    path('members/', views.MemberListView.as_view(), name='member_list'),
    path('members/new/', views.MemberCreateView.as_view(), name='member_create'),
    path('members/<int:pk>/book/', views.MemberBookView.as_view(), name='member_book'),
    path('members/<int:pk>/record/', views.RecordEntryView.as_view(), name='record_entry'),
    
    # 4. Customer Access (Regular member views)
    path('my-book/<int:pk>/', views.CustomerBookView.as_view(), name='customer_view'),
]