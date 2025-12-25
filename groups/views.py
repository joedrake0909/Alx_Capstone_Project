from django import forms
from django.views.generic import ListView, CreateView, DetailView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Sum, Q
from django.views.generic.edit import UpdateView
import string
from django.db import transaction
from django.utils import timezone

# Import your models
from .models import Member, Cycle, Group, DigitalBook, Page, Entry
from .forms import ExampleForm

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
    
    def get_queryset(self):
        # 🌟 USE select_related to grab the Developer and User in ONE database hit
        return Group.objects.select_related('developer__user').all().order_by('-created_at')
    
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
    login_url = '/login/'
    template_name = 'groups/member_list.html'
    model = Member
    context_object_name = 'members'

    def test_func(self):
        return is_admin(self.request.user)
    
    def get_queryset(self):
        # 1. Start by filtering members belonging to this Admin's group
        if self.request.user.is_superuser:
            queryset = Member.objects.all()
        else:
            try:
                admin_group = Group.objects.get(admin=self.request.user)
                queryset = Member.objects.filter(group=admin_group)
            except Group.DoesNotExist:
                return Member.objects.none()

        # 2. Then apply the search filter if one exists
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(full_name__icontains=query) | 
                Q(member_id__icontains=query) |
                Q(phone_number__icontains=query)
            )
            
        return queryset.order_by('joined_at')


class MemberCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Registration: Creates User, Book, and 20 Pages automatically with custom ID."""
    login_url = '/login/'
    template_name = 'groups/member_form.html'
    model = Member
    fields = ['full_name', 'phone_number', 'group']
    success_url = reverse_lazy('member_list')

    def test_func(self):
        return is_admin(self.request.user)

    def form_valid(self, form):
        # 1. Create the User Account
        base_name = form.cleaned_data['full_name'].replace(" ", "").lower()
        username = base_name
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_name}{counter}"
            counter += 1
        new_user = User.objects.create_user(username=username, password='password123')

        # 2. Save Member 
        member = form.save(commit=False)
        member.user = new_user
        # We explicitly set this just in case auto_now_add is being stubborn
        member.joined_at = timezone.now() 
        member.status = 'ACTIVE'
        member.save() 

        messages.success(self.request, f"Successfully registered {member.full_name}!")
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
        member = self.object
        page_num = int(self.request.GET.get('page', 1))
        
        # Ensure the member has an active book
        book = member.current_book
        if not book:
            # Fallback: find any book belonging to them
            book = DigitalBook.objects.filter(member=member).first()
            if book:
                member.current_book = book
                member.save(update_fields=['current_book'])

        if book:
            # Get or create the specific page for this book
            page, _ = Page.objects.get_or_create(digital_book=book, page_number=page_num)
            
            # Fetch entries and turn them into a dictionary for row-lookup
            # This is much faster and more reliable than multiple .filter() calls in a loop
            entries_dict = {e.row_number: e for e in page.entries.all()}
            
            rows = []
            for i in range(1, 32):
                rows.append({
                    'number': i, 
                    'data': entries_dict.get(i)  # Finds the entry for this row if it exists
                })
            
            context['rows'] = rows
            context['current_page'] = page
            context['book'] = book
        else:
            context['error'] = "No digital book found for this member."
            
        return context


class RecordEntryView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Entry
    fields = ['deposit_amount', 'withdrawal_amount', 'date']
    template_name = 'groups/record_entry_form.html'

    def test_func(self):
        return is_admin(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        member = get_object_or_404(Member, id=self.kwargs['pk'])
        context['target_member'] = member
        context['page_num'] = self.request.GET.get('page', 1)
        return context

    def get_next_available_slot(self, target_member):
        """Find the first empty row in the current or specified book."""
        # Check if a specific book was requested via URL
        requested_book_id = self.request.GET.get('book')
        if requested_book_id:
            book = DigitalBook.objects.filter(id=requested_book_id, member=target_member).first()
        else:
            book = target_member.current_book

        if not book:
            # Final fallback: Get their most recent book
            book = DigitalBook.objects.filter(member=target_member).order_by('-book_number').first()
        
        # If still no book, create one
        if not book:
            book = DigitalBook.objects.create(member=target_member, book_number=1)
            # Create pages for the new book
            for i in range(1, 21):
                Page.objects.create(digital_book=book, page_number=i)
            target_member.current_book = book
            target_member.save(update_fields=['current_book'])

        # Check pages in order
        for p_num in range(1, 21):
            page, _ = Page.objects.get_or_create(digital_book=book, page_number=p_num)
            occupied_rows = page.entries.values_list('row_number', flat=True)
            for r_num in range(1, 32):
                if r_num not in occupied_rows:
                    return page, r_num
        
        # If all pages are full, create a new book
        last_book_num = DigitalBook.objects.filter(member=target_member).aggregate(
            max_book=models.Max('book_number')
        )['max_book'] or 0
        
        new_book_num = last_book_num + 1
        new_book = DigitalBook.objects.create(member=target_member, book_number=new_book_num)
        
        # Create pages for the new book
        for i in range(1, 21):
            Page.objects.create(digital_book=new_book, page_number=i)
        
        target_member.current_book = new_book
        target_member.save(update_fields=['current_book'])
        
        # Return first row of first page in new book
        first_page = Page.objects.get(digital_book=new_book, page_number=1)
        return first_page, 1

    def form_valid(self, form):
        member = get_object_or_404(Member, id=self.kwargs['pk'])
        fixed_rate = member.group.fixed_deposit_amount
        
        deposit = form.cleaned_data.get('deposit_amount', 0)
        withdrawal = form.cleaned_data.get('withdrawal_amount', 0)
        entry_date = form.cleaned_data.get('date')

        with transaction.atomic():
            if deposit and deposit > 0:
                # Math: How many rows does this deposit cover?
                num_rows = max(1, int(deposit // fixed_rate))
                
                for _ in range(num_rows):
                    target_page, target_row = self.get_next_available_slot(member)
                    if target_page:
                        Entry.objects.create(
                            member=member,
                            page=target_page,
                            row_number=target_row,
                            date=entry_date,
                            deposit_amount=fixed_rate if num_rows > 1 else deposit,
                            status='APPROVED'
                        )
            elif withdrawal and withdrawal > 0:
                target_page, target_row = self.get_next_available_slot(member)
                if target_page:
                    Entry.objects.create(
                        member=member,
                        page=target_page,
                        row_number=target_row,
                        date=entry_date,
                        withdrawal_amount=withdrawal,
                        status='APPROVED'
                    )

        messages.success(self.request, "Transaction successfully added to ledger.")
        return redirect('member_book', pk=member.id)


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
            
        page_num = int(self.request.GET.get('page', 1))
        
        try:
            book = self.object.current_book
            if not book:
                # Fallback: find any book belonging to them
                book = DigitalBook.objects.filter(member=self.object).first()
                if book:
                    self.object.current_book = book
                    self.object.save(update_fields=['current_book'])
            
            if book:
                page, _ = Page.objects.get_or_create(digital_book=book, page_number=page_num)
                
                # Create the 31-row structure
                entries_dict = {e.row_number: e for e in page.entries.all()}
                rows = []
                for i in range(1, 32):
                    rows.append({'number': i, 'data': entries_dict.get(i)})
                
                context['rows'] = rows
                context['current_page'] = page
                context['book'] = book
                
                # Calculate total balance for this member
                total_deposits = Entry.objects.filter(member=self.object).aggregate(
                    total=Sum('deposit_amount')
                )['total'] or 0
                total_withdrawals = Entry.objects.filter(member=self.object).aggregate(
                    total=Sum('withdrawal_amount')
                )['total'] or 0
                context['member_balance'] = total_deposits - total_withdrawals
            else:
                context['error'] = "No digital book found."
                
        except Exception as e:
            context['error'] = f"Error loading book: {str(e)}"
        
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
    fields = ['phone_number']  # Strictly restrict to phone only
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
        group = form.save()
        messages.success(self.request, f"Successfully created group: {group.name}")
        return redirect(self.success_url)