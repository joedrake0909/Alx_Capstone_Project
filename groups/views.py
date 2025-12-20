from django import forms
from django.views.generic import ListView, CreateView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Sum
from django.views.generic.edit import UpdateView

# Import your models
from .models import Member, Cycle, Group, DigitalBook
from contributions.models import Entry, Page

# --- HELPERS ---

def is_admin(user):
    """Helper to check if the user is a superuser (Treasurer)."""
    return user.is_superuser

class DateInput(forms.DateInput):
    """Helper to force HTML5 date picker in forms."""
    input_type = 'date'

# --- SUPERUSER DASHBOARD VIEWS (The Master Control Panel) ---

class SuperuserDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """MASTER DASHBOARD: The Stats Page for superuser."""
    template_name = 'groups/superuser_dashboard.html'
    login_url = '/login/'

    def test_func(self):
        return self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Stats for Dashboard icons
        context['total_groups'] = Group.objects.count()
        context['total_users'] = Member.objects.count()
        context['total_savings'] = Entry.objects.aggregate(Sum('deposit_amount'))['deposit_amount__sum'] or 0
        return context


class AdminUserListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """ADMIN MENU: List of Group Admins/Treasurers with their groups."""
    model = Group
    template_name = 'groups/admin_user_list.html'
    context_object_name = 'admin_groups'
    login_url = '/login/'

    def test_func(self):
        return self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any additional context if needed
        return context


class AllTransactionsView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """TRANSACTIONS MENU: All money moves, latest first."""
    model = Entry
    template_name = 'groups/all_transactions.html'
    context_object_name = 'transactions'
    
    def test_func(self):
        return self.request.user.is_superuser

    def get_queryset(self):
        # Latest transactions at the top
        return Entry.objects.all().select_related('member', 'member__group').order_by('-date', '-id')


# --- REGULAR ADMIN VIEWS (For Group Treasurers) ---

class MemberListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Admin Directory: List all members."""
    login_url = '/login/'
    template_name = 'groups/member_list.html'
    model = Member
    context_object_name = 'members'

    def test_func(self):
        return is_admin(self.request.user)
    
    def get_queryset(self):
        # FIX: Instead of getting one group (which crashes if you have 4),
        # we show ALL members since you are the Superadmin.
        if self.request.user.is_superuser:
            return Member.objects.select_related('group').all().order_by('-id')
        
        # Keep original logic for regular admins (if any)
        try:
            admin_group = Group.objects.get(admin=self.request.user)
            return Member.objects.filter(group=admin_group).order_by('joined_at')
        except (Group.DoesNotExist, Group.MultipleObjectsReturned):
            return Member.objects.none()


class MemberCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Registration: Creates User, Book, and 20 Pages automatically."""
    login_url = '/login/'
    template_name = 'groups/member_form.html'
    model = Member
    fields = ['full_name', 'phone_number', 'group']  # Added 'group' back to fields
    success_url = reverse_lazy('member_list')

    def test_func(self):
        return is_admin(self.request.user)

    def form_valid(self, form):
        # 1. Get the selected group from the form
        selected_group = form.cleaned_data['group']
        
        # 2. Generate User
        base_name = form.cleaned_data['full_name'].replace(" ", "").lower()
        username = base_name
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_name}{counter}"
            counter += 1
        
        new_user = User.objects.create_user(username=username, password='password123')

        # 3. Create Book
        last_book = DigitalBook.objects.order_by('-book_number').first()
        next_num = (last_book.book_number + 1) if last_book else 1
        new_book = DigitalBook.objects.create(book_number=next_num)

        # 4. Create 20 Pages (Bulk)
        pages = [Page(digital_book=new_book, page_number=i) for i in range(1, 21)]
        Page.objects.bulk_create(pages)

        # 5. Save Member
        member = form.save(commit=False)
        member.user = new_user
        # Use the selected group from the form instead of auto-assigning
        member.group = selected_group
        member.digital_book = new_book
        member.status = 'ACTIVE'
        member.save()

        messages.success(self.request, f"Registered {member.full_name}! Book #{next_num} ready.")
        return redirect(self.success_url)


class MemberBookView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Ledger View: Displays the 31-row grid for a specific page."""
    model = Member
    template_name = 'groups/book_view.html'
    context_object_name = 'member'

    def test_func(self):
        return is_admin(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page_num = self.request.GET.get('page', 1)
        
        try:
            page = Page.objects.get(digital_book=self.object.digital_book, page_number=page_num)
            existing_entries = page.entries.all()
            
            # Create the 31-row structure
            rows = []
            for i in range(1, 32):
                entry = existing_entries.filter(row_number=i).first()
                rows.append({'number': i, 'data': entry})
            
            context['rows'] = rows
            context['current_page'] = page
        except Page.DoesNotExist:
            context['error'] = "Book pages missing."
        return context


class RecordEntryView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    # ... (keep existing fields and get_form/get_initial) ...

    def form_valid(self, form):
        member = Member.objects.get(id=self.kwargs['pk'])
        row_num = int(self.request.GET.get('row', 1))
        page_num = int(self.request.GET.get('page', 1))
        page = Page.objects.get(digital_book=member.digital_book, page_number=page_num)
        
        form.instance.member = member
        form.instance.page = page
        form.instance.row_number = row_num
        form.instance.status = 'APPROVED'

        # FIX: Pull the PREVIOUS balance so we don't start at 0 every time
        last_entry = Entry.objects.filter(member=member).order_by('-date', '-row_number', '-id').first()
        previous_balance = last_entry.current_balance if last_entry else 0

        deposit = form.cleaned_data.get('deposit_amount', 0)
        withdrawal = form.cleaned_data.get('withdrawal_amount', 0)
        
        # CORRECT MATH: New Balance = Previous + Deposit - Withdrawal
        form.instance.current_balance = previous_balance + deposit - withdrawal

        messages.success(self.request, f"Entry saved! New Balance: {form.instance.current_balance}")
        return super().form_valid(form)


# --- CUSTOMER VIEWS (For Regular Members) ---

class CustomerBookView(LoginRequiredMixin, DetailView):
    """Regular member's view of their own digital book."""
    model = Member
    template_name = 'groups/customer_book.html'
    context_object_name = 'member'
    
    def get_object(self):
        """Ensure members can only view their own book."""
        # Get the member profile for the logged-in user
        member = get_object_or_404(Member, user=self.request.user)
        
        # Additional security: check if the URL pk matches the user's member id
        if str(member.id) != self.kwargs.get('pk'):
            messages.error(self.request, "You can only view your own digital book.")
            return None
        return member
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        if self.object is None:
            return context
            
        page_num = self.request.GET.get('page', 1)
        
        try:
            page = Page.objects.get(digital_book=self.object.digital_book, page_number=page_num)
            existing_entries = page.entries.all()
            
            # Create the 31-row structure (similar to MemberBookView)
            rows = []
            for i in range(1, 32):
                entry = existing_entries.filter(row_number=i).first()
                rows.append({'number': i, 'data': entry})
            
            context['rows'] = rows
            context['current_page'] = page
            
            # Calculate total balance for this member
            total_deposits = Entry.objects.filter(member=self.object).aggregate(
                total=Sum('deposit_amount')
            )['total'] or 0
            total_withdrawals = Entry.objects.filter(member=self.object).aggregate(
                total=Sum('withdrawal_amount')
            )['total'] or 0
            context['member_balance'] = total_deposits - total_withdrawals
            
        except Page.DoesNotExist:
            context['error'] = "Book pages not found."
        
        return context


# --- AUTHENTICATION VIEW ---

def login_success(request):
    """Slingshot users to their respective homes after login."""
    if request.user.is_superuser:
        # Redirect Superuser to the NEW Dashboard
        return redirect('super_dashboard')
    else:
        # Redirect regular Member to their Digital Book
        try:
            member = request.user.member
            return redirect('customer_view', pk=member.id)
        except AttributeError:
            return redirect('/')

class MemberProfileUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Member
    fields = ['phone_number'] # Strictly restrict to phone only
    template_name = 'groups/profile_settings.html'
    
    def test_func(self):
        # Ensure members can only edit their own profile
        return self.request.user == self.get_object().user

    def get_success_url(self):
        return reverse_lazy('customer_view', kwargs={'pk': self.object.id})
    

def landing_page(request):
    # If a user is already logged in, send them to their dashboard instead of the landing page
    if request.user.is_authenticated:
        return redirect('login_success')
    return render(request, 'landing.html')



class GroupCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Group
    fields = ['name'] # You only need to provide the name (e.g., "Makata Market Women")
    template_name = 'groups/group_form.html'
    success_url = reverse_lazy('super_dashboard')

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form):
        # Automatically set the Superadmin as the manager of this group
        form.instance.admin = self.request.user
        return super().form_valid(form)