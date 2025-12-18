from django import forms
from django.views.generic import ListView, CreateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.models import User

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

# --- VIEWS ---

class MemberListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Admin Directory: List all members in the Treasurer's group."""
    login_url = '/login/'
    template_name = 'groups/member_list.html'
    model = Member
    context_object_name = 'members'

    def test_func(self):
        return is_admin(self.request.user)
    
    def get_queryset(self):
        try:
            admin_group = Group.objects.get(admin=self.request.user)
            return Member.objects.filter(group=admin_group).order_by('joined_at')
        except Group.DoesNotExist:
            return Member.objects.none()


class MemberCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Registration: Creates User, Book, and 20 Pages automatically."""
    login_url = '/login/'
    template_name = 'groups/member_form.html'
    model = Member
    fields = ['full_name', 'phone_number']
    success_url = reverse_lazy('member_list')

    def test_func(self):
        return is_admin(self.request.user)

    def form_valid(self, form):
        # 1. Get Group
        try:
            admin_group = Group.objects.get(admin=self.request.user)
        except Group.DoesNotExist:
            messages.error(self.request, "Setup Error: Admin group not found.")
            return self.render_to_response(self.get_context_data(form=form))

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
        member.group = admin_group
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
    """Entry Form: Saves data to a specific row and page."""
    model = Entry
    template_name = 'groups/entry_form.html'
    fields = ['date', 'deposit_amount', 'withdrawal_amount']
    
    def test_func(self):
        return is_admin(self.request.user)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['date'].widget = DateInput()
        return form

    def get_initial(self):
        initial = super().get_initial()
        from datetime import date
        initial['date'] = date.today()
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['target_member'] = Member.objects.get(id=self.kwargs['pk'])
        context['row_num'] = self.request.GET.get('row')
        context['page_num'] = self.request.GET.get('page')
        return context

    def form_valid(self, form):
        member = Member.objects.get(id=self.kwargs['pk'])
        row_num = int(self.request.GET.get('row', 1))
        page_num = int(self.request.GET.get('page', 1))

        page = Page.objects.get(digital_book=member.digital_book, page_number=page_num)
        
        form.instance.member = member
        form.instance.page = page
        form.instance.row_number = row_num
        form.instance.status = 'APPROVED'

        # Math logic
        deposit = form.cleaned_data.get('deposit_amount', 0)
        withdrawal = form.cleaned_data.get('withdrawal_amount', 0)
        form.instance.current_balance = deposit - withdrawal

        messages.success(self.request, f"Entry saved to Row {row_num}!")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('member_book', kwargs={'pk': self.kwargs['pk']})
    

def login_success(request):
        #Traffic controller: Redirects users based on their role 
        # immediately after they log in.

        if request.user.is_superuser:
            return redirect('member_list')
        else:
            # # A normal member goes to their personal digital book
            #  We find the member object linked to this user
            try:
                member = request.user.member
                return redirect('customer_view', pk=member.id)
            except AttributeError:
                # fallback if user is not a superuser or member
                return redirect('/')
                
    