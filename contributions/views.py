from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.shortcuts import redirect

# Check if user is admin
def is_admin(user):
    return user.is_superuser

# The core admin dashboard view
@login_required(login_url='login')
@user_passes_test(is_admin, login_url='login')

def dashboard_view(request):
    #Admin landing page showing group totals

    context = {
        'page_title': 'Admin Dashboard',
        'admin_message': 'Welcome to the Admin Control Panel.This view is secured!',
    }
    return render(request, 'dashboard.html', context)





# Create your views here.
