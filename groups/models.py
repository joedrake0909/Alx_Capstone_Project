from django.db import models
from django.contrib.auth.models import User
import string
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

def generate_next_member_id(group):
    count = Member.objects.filter(group=group).count() + 1
    if count <= 9999:
        return f"{count:04d}"
    overflow_count = count - 9999
    letter_index = (overflow_count - 1) // 999
    number_part = (overflow_count - 1) % 999 + 1
    alphabet = string.ascii_uppercase
    if letter_index < len(alphabet):
        prefix = alphabet[letter_index]
        return f"{prefix}{number_part:03d}"
    return f"EXT{count}"

class Developer(models.Model):
    name = models.CharField(max_length=100)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='developer')
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return self.name

class Group(models.Model):
    GROUP_TYPE_CHOICES = [('regular', 'Regular Savings'), ('rotating', 'Rotating Fund'), ('investment', 'Investment Group')]
    developer = models.ForeignKey(Developer, on_delete=models.CASCADE, related_name='managed_groups', null=True, blank=True)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    group_type = models.CharField(max_length=20, choices=GROUP_TYPE_CHOICES, default='rotating')
    fixed_deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    max_members = models.PositiveIntegerField(default=50)
    cycle_duration_days = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
    def __str__(self): return f"{self.name} ({self.get_group_type_display()})"
    
    @property
    def active_members_count(self): return self.members.filter(status='ACTIVE').count()

class Cycle(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='cycles')
    cycle_number = models.PositiveIntegerField()
    pot_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=10, choices=[('PLANNED', 'Planned'), ('ACTIVE', 'Active')], default='PLANNED')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('group', 'cycle_number')
    def __str__(self): return f"{self.group.name} - Cycle {self.cycle_number}"

class Member(models.Model):
    """Member belonging to a savings group"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='member_profile',
        null=True, 
        blank=True,
        help_text="Linked Django user account for login"
    )
    
    member_id = models.CharField(max_length=10, blank=True, editable=False)
    full_name = models.CharField(max_length=255, help_text="The full name of the member.")
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    
    group = models.ForeignKey(
        'Group',
        on_delete=models.CASCADE,
        related_name='members'
    )
    
    # Status of the member
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('PENDING', 'Pending'),
        ('SUSPENDED', 'Suspended'),
        ('GRADUATED', 'Graduated'),
    ]
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PENDING'
    )
    
    # Defines the order in which the member receives the pot
    payout_order = models.PositiveIntegerField(
        null=True, 
        blank=True,
        help_text="The sequence number for receiving the pot in the group."
    )
    
    # Member's position in the current cycle
    current_cycle_position = models.PositiveIntegerField(null=True, blank=True)
    
    # Additional member information
    joined_at = models.DateTimeField(auto_now_add=True)
    last_contribution_date = models.DateField(null=True, blank=True)
    
    # UPDATED: Added null=True, blank=True for these fields
    total_contributions = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        null=True,
        blank=True,
        help_text="Total contributions made by this member"
    )
    total_payouts = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        null=True,
        blank=True,
        help_text="Total payouts received by this member"
    )
    
    # Emergency contact info
    emergency_contact_name = models.CharField(max_length=255, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    
    # Track current book for quick access
    current_book = models.ForeignKey(
        'DigitalBook',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_member',
        help_text="Member's current active digital book"
    )
    
    class Meta:
        unique_together = ('user', 'group')
        ordering = ['payout_order', 'joined_at']
    
    def __str__(self):
        return f"{self.full_name} ({self.member_id}) - {self.group.name}"
    
    def save(self, *args, **kwargs):
        """Auto-generate ID and handle circular Book creation safely."""
        if not self.member_id:
            self.member_id = generate_next_member_id(self.group)
        
        # Check if this is a new member before saving
        is_new = self.pk is None
        
        # We pop update_fields to avoid errors during the circular save process
        update_fields = kwargs.pop('update_fields', None)
        super().save(*args, **kwargs)

        # Now that Member has an ID, create the first book if needed
        if is_new and self.status == 'ACTIVE' and not self.current_book:
            new_book = DigitalBook.objects.create(member=self, book_number=1)
            
            # Create the 20 pages immediately
            pages = [Page(digital_book=new_book, page_number=i) for i in range(1, 21)]
            Page.objects.bulk_create(pages)
            
            # Link back to member and save again
            self.current_book = new_book
            super().save(update_fields=['current_book'])
        
        # Auto-assign payout_order if not set and group is rotating type
        if not self.payout_order and self.group.group_type == 'rotating':
            last_member = Member.objects.filter(group=self.group).exclude(payout_order=None).order_by('-payout_order').first()
            self.payout_order = (last_member.payout_order + 1) if last_member else 1
        
        super().save(*args, **kwargs)
    
    @property
    def current_digital_book(self):
        """Get the current digital book for this member"""
        return self.current_book
    
    @property
    def all_digital_books(self):
        """Get all digital books for this member"""
        return self.books.all().order_by('book_number')
    
    @property
    def net_balance(self):
        """Calculate member's net balance (contributions - payouts)"""
        return (self.total_contributions or 0) - (self.total_payouts or 0)
    
    @property
    def is_payment_current(self):
        """Check if member's payments are up to date"""
        if not self.last_contribution_date:
            return False
        
        # Logic to check if last contribution was within current cycle
        # You would need to implement this based on your cycle logic
        return True

class DigitalBook(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='books')
    book_number = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('member', 'book_number')

class Page(models.Model):
    digital_book = models.ForeignKey(DigitalBook, on_delete=models.CASCADE, related_name='pages')
    page_number = models.PositiveIntegerField()
    class Meta:
        unique_together = ('digital_book', 'page_number')

class Entry(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='entries')
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='entries')
    row_number = models.PositiveIntegerField()
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    withdrawal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    date = models.DateField(default=timezone.now)
    status = models.CharField(max_length=10, default='APPROVED')

    class Meta:
        unique_together = ('page', 'row_number')
        ordering = ['page', 'row_number']

    def save(self, *args, **kwargs):
        if not self.pk:
            last_entry = Entry.objects.filter(member=self.member, page=self.page).order_by('-row_number').first()
            prev_bal = last_entry.current_balance if last_entry else Decimal('0.00')
            
            if self.deposit_amount > 0:
                self.current_balance = prev_bal + Decimal(str(self.deposit_amount))
            elif self.withdrawal_amount > 0:
                self.current_balance = prev_bal - Decimal(str(self.withdrawal_amount))
        super().save(*args, **kwargs)