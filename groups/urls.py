from django.urls import path
from . import views


urlpatterns = [
    # Member List View
    path('members/', views.MemberListView.as_view(), name='member_list'),

    # Member Create View
    path('members/new/', views.MemberCreateView.as_view(), name='member_create'),

    path('members/<int:member_id>/record/', views.RecordEntryView.as_view(), name='record_entry'),

    
]

