from django.urls import path
from . import views

urlpatterns = [
    # Mapped to the /dashboard/ URL
    path('dashboard/', views.dashboard_view, name='dashboard')
]

