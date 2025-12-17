from django.urls import path
from . import views

urlpatterns = [
    path('members/', views.MemberListView.as_view(), name='member_list'),
    path('members/new/', views.MemberCreateView.as_view(), name='member_create'),
    
    # We use 'pk' for both to keep it simple and consistent
    path('members/<int:pk>/book/', views.MemberBookView.as_view(), name='member_book'),
    path('members/<int:pk>/record/', views.RecordEntryView.as_view(), name='record_entry'),
]