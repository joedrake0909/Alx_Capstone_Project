from django.views.generic import ListView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from . models import Member, Cycle, Group, DigitalBook
from contributions.models import Entry, Page
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.models import User



def is_admin(user):
    return user.is_superuser

# member list view
class MemberListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    # Security mixins
    login_url = '/login/'
    template_name = 'groups/member_list.html'

    # Permission check: only admin can view all members
    def test_func(self):
        return is_admin(self.request.user)
    
    model = Member
    context_object_name = 'members'

    # Ensure the list only shows members belonging to the current group
    def get_queryset(self):
        try:
            admin_group = Group.objects.get(admin=self.request.user)
            return Member.objects.filter(group=admin_group).order_by('joined_at')
        except Group.DoesNotExist:
            return Member.objects.none()
        

# Member create view
class MemberCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    # Scurity mixins
    login_url = '/login/'
    template_name = 'groups/member_form.html'

    # Permission check: only admin can create members
    def test_func(self):
        return is_admin(self.request.user)
    
    model = Member
    fields = ['full_name', 'phone_number']

    success_url = reverse_lazy('member_list')

    def form_valid(self, form):
        # 1. Get the Admin's Group
        try:
            admin_group = Group.objects.get(admin=self.request.user)
        except Group.DoesNotExist:
            messages.error(self.request, "Setup Error: You don't have a Group assigned to your Admin account.")
            return self.render_to_response(self.get_context_data(form=form))

        # 2. Generate a Unique Username
        base_name = form.cleaned_data['full_name'].replace(" ", "").lower()
        username = base_name
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_name}{counter}"
            counter += 1

        # 3. Create the Django User
        new_user = User.objects.create_user(
            username=username,
            password='password123' # Default password to be changed later
        )

        # 4. Create the Digital Book
        # We find the highest book number and add 1
        last_book = DigitalBook.objects.order_by('-book_number').first()
        next_book_num = (last_book.book_number + 1) if last_book else 1
        new_book = DigitalBook.objects.create(book_number=next_book_num)

        # 5. 🌟 NEW: GENERATE THE 20 PAGES
        # This loop creates the fixed structure of your physical ledger
        pages_to_create = []
        for i in range(1, 21):  # 1 to 20 inclusive
            pages_to_create.append(Page(digital_book=new_book, page_number=i))
        
        # bulk_create is much faster than saving 20 times!
        Page.objects.bulk_create(pages_to_create)

        # 6. Link and Save the Member
        member = form.save(commit=False)
        member.user = new_user
        member.group = admin_group
        member.digital_book = new_book
        member.status = 'ACTIVE'
        member.save()

        messages.success(self.request, f"Registered {member.full_name}! Book #{new_book.book_number} created with 20 pages.")
        return redirect(self.success_url)




class RecordEntryView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Entry
    template_name = 'groups/entry_form.html'
    fields = ['date', 'row_number', 'deposit_amount', 'withdrawal_amount', 'status']
    
    def test_func(self):
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        # This helps us show which member we are recording for in the HTML
        context = super().get_context_data(**kwargs)
        context['target_member'] = Member.objects.get(id=self.kwargs['member_id'])
        return context

    def form_valid(self, form):
        member = Member.objects.get(id=self.kwargs['member_id'])
        
        # 1. Logic to find the correct Page object
        # For now, we default to Page 1. Later we can make this dynamic.
        page = Page.objects.get(digital_book=member.digital_book, page_number=1)
        
        # 2. Calculate the Balance (Simplified for now)
        # Balance = Deposit - Withdrawal
        deposit = form.cleaned_data.get('deposit_amount', 0)
        withdrawal = form.cleaned_data.get('withdrawal_amount', 0)
        form.instance.current_balance = deposit - withdrawal
        
        # 3. Attach the hidden fields
        form.instance.member = member
        form.instance.page = page
        
        messages.success(self.request, f"Entry recorded for {member.full_name}")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('member_list')



