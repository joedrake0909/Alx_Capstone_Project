from django.views.generic import ListView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from . models import Member, Cycle, Group


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
            admin_group = Group.objects.get(admin_user=self.request.user)
            return Member.objects.filter(group=admin_group)
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
    fields = ['full name', 'phone_number']

    success_url = reverse_lazy('member_list')

    def form_valid(self, form):
        admin_group = Group.objects.get(admin_user=self.request.user)
        form.instance.group = admin_group
        return super().form_valid(form)
    








