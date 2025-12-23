from django import forms
from django.views.generic import ListView, CreateView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Sum
from django.views.generic.edit import UpdateView
import string

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
    """Registration: Creates User, Book, and 20 Pages automatically with custom ID."""
    login_url = '/login/'
    template_name = 'groups/member_form.html'
    model = Member
    fields = ['full_name', 'phone_number', 'group']
    success_url = reverse_lazy('member_list')

    def test_func(self):
        return is_admin(self.request.user)

    # 🌟 INTERNAL LOGIC FOR ID GENERATION
    def get_next_member_id(self, group):
        """Generates 0001-9999 then A001-Z999 based on group count."""
        count = Member.objects.filter(group=group).count() + 1
        
        if count <= 9999:
            return f"{count:04d}"
        
        overflow = count - 9999
        letter_idx = (overflow - 1) // 999
        num_part = (overflow - 1) % 999 + 1
        
        if letter_idx < len(string.ascii_uppercase):
            prefix = string.ascii_uppercase[letter_idx]
            return f"{prefix}{num_part:03d}"
        return f"EXT{count}"

    def form_valid(self, form):
        selected_group = form.cleaned_data['group']
        
        # 🌟 CALL THE INTERNAL METHOD
        new_member_id = self.get_next_member_id(selected_group)
        
        # --- Generate User ---
        base_name = form.cleaned_data['full_name'].replace(" ", "").lower()
        username = base_name
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_name}{counter}"
            counter += 1
        
        new_user = User.objects.create_user(username=username, password='password123')

        # --- Create Book ---
        new_book = DigitalBook.objects.create(book_number=1)

        # --- Create Pages ---
        pages = [Page(digital_book=new_book, page_number=i) for i in range(1, 21)]
        Page.objects.bulk_create(pages)

        # --- Save Member ---
        member = form.save(commit=False)
        member.user = new_user
        member.group = selected_group
        member.member_id = new_member_id # 🌟 SET THE NEW ID
        member.digital_book = new_book
        member.status = 'ACTIVE'
        member.save()

        messages.success(self.request, f"Registered {member.full_name}! ID: {new_member_id}")
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


from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from groups.models import Entry, Member, Page, DigitalBook
from groups.utils import is_admin
from django.utils import timezone

class RecordEntryView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Entry
    fields = ['deposit_amount', 'withdrawal_amount', 'date']
    template_name = 'groups/record_entry_form.html'

    def test_func(self):
        return is_admin(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        member = get_object_or_404(Member, id=self.kwargs['pk'])
        
        # Get current page from URL or default to 1
        page_num = self.request.GET.get('page', 1)
        
        context['target_member'] = member
        context['page_num'] = page_num
        
        # Calculate current row number for display (next available row on current page)
        try:
            current_book = member.digital_book
            current_page = Page.objects.get(digital_book=current_book, page_number=page_num)
            occupied_rows = current_page.entries.values_list('row_number', flat=True)
            # Find first empty row on this page
            next_row = next((i for i in range(1, 32) if i not in occupied_rows), 1)
            context['row_num'] = next_row
        except (DigitalBook.DoesNotExist, Page.DoesNotExist):
            context['row_num'] = 1
        
        return context

    def form_valid(self, form):
        member = get_object_or_404(Member, id=self.kwargs['pk'])
        fixed_rate = member.group.fixed_deposit_amount
        total_deposit = form.cleaned_data.get('deposit_amount', 0)
        withdrawal = form.cleaned_data.get('withdrawal_amount', 0)
        entry_date = form.cleaned_data.get('date')

        with transaction.atomic():
            # Find the active page/row
            target_page, target_row = self.get_next_available_slot(member)
            
            # 🌟 BOOK-ISOLATED BALANCE LOOKUP
            # We only look for the last entry IN THE SAME BOOK as our target page
            last_entry = Entry.objects.filter(
                member=member, 
                page__digital_book=target_page.digital_book
            ).order_items('-page__page_number', '-row_number').first()
            
            # If it's a new book, current_bal starts at 0 automatically
            current_bal = last_entry.current_balance if last_entry else 0

            # --- PROCESS WITHDRAWAL ---
            if withdrawal > 0:
                if withdrawal > current_bal:
                    messages.error(self.request, "Insufficient balance in this book!")
                    return redirect(self.request.path)
                
                Entry.objects.create(
                    member=member, page=target_page, row_number=target_row,
                    date=entry_date, withdrawal_amount=withdrawal,
                    current_balance=current_bal - withdrawal, status='APPROVED'
                )

            # --- PROCESS DEPOSIT (Overflow) ---
            elif total_deposit > 0:
                num_rows = int(total_deposit // fixed_rate)
                for _ in range(num_rows):
                    # Re-check slot in case the loop pushes us to a new page/book
                    target_page, target_row = self.get_next_available_slot(member)
                    
                    # Re-calculate balance if we just jumped into a brand new book
                    last_entry_in_loop = Entry.objects.filter(
                        member=member, 
                        page__digital_book=target_page.digital_book
                    ).order_by('-page__page_number', '-row_number').first()
                    
                    loop_bal = last_entry_in_loop.current_balance if last_entry_in_loop else 0
                    new_bal = loop_bal + fixed_rate
                    
                    Entry.objects.create(
                        member=member, page=target_page, row_number=target_row,
                        date=entry_date, deposit_amount=fixed_rate,
                        current_balance=new_bal, status='APPROVED'
                    )

        messages.success(self.request, "Transaction recorded. New book started at zero if applicable.")
        return redirect('member_book', pk=member.id)
    
    def get_form(self, form_class=None):
        """Customize form initialization"""
        form = super().get_form(form_class)
        
        # Set initial values
        member = get_object_or_404(Member, id=self.kwargs['pk'])
        
        # Pre-fill date with today
        form.fields['date'].initial = timezone.now().date()
        
        # Optionally pre-fill deposit amount with group fixed rate
        if 'deposit_amount' in form.fields:
            form.fields['deposit_amount'].initial = member.group.fixed_deposit_amount
        
        return form
    
    def get_success_url(self):
        """Define the success URL"""
        member = get_object_or_404(Member, id=self.kwargs['pk'])
        return reverse_lazy('member_book', kwargs={'pk': member.id})



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
    fields = ['name', 'fixed_deposit_amount'] 
    template_name = 'groups/group_form.html'
    success_url = reverse_lazy('super_dashboard')

    def test_func(self):
        return self.request.user.is_superuser

    def form_valid(self, form):
        # Automatically set the Superadmin as the manager of this group
        form.instance.admin = self.request.user
        return super().form_valid(form)