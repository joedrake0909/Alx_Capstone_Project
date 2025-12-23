from django.db import models
from django.contrib.auth.models import User
import string
from django.core.exceptions import ValidationError

def generate_next_member_id(group):
    """
    Logic: 
    0001-9999
    Then A001-A999, B001-B999, etc.
    """
    count = Member.objects.filter(group=group).count() + 1
    
    # 1. Standard numbering (1 to 9999)
    if count <= 9999:
        return f"{count:04d}" # Pads with zeros: 0001, 0002...
    
    # 2. Alphanumeric numbering (A001, B001...)
    # We subtract 9999 because we are starting a new set
    overflow_count = count - 9999
    letter_index = (overflow_count - 1) // 999  # 0 for A, 1 for B...
    number_part = (overflow_count - 1) % 999 + 1
    
    alphabet = string.ascii_uppercase # A-Z
    if letter_index < len(alphabet):
        prefix = alphabet[letter_index]
        return f"{prefix}{number_part:03d}"
    
    return f"EXT{count}" # Fallback if you exceed Z999

class Developer(models.Model):
    """Developer/Partner who creates and manages groups"""
    name = models.CharField(max_length=100)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='developer')
    # Add other developer fields as needed
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class SavingsGroup(models.Model):
    """Main group model with improved structure"""
    GROUP_TYPE_CHOICES = [
        ('regular', 'Regular Savings'),
        ('rotating', 'Rotating Fund'),
        ('investment', 'Investment Group'),
    ]
    
    developer = models.ForeignKey(
        Developer, 
        on_delete=models.CASCADE,
        related_name='managed_groups',
        help_text="The developer/partner who created this group"
    )
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    group_type = models.CharField(
        max_length=20, 
        choices=GROUP_TYPE_CHOICES,
        default='rotating'
    )
    
    # Store the specific fixed contribution amount for this group
    fixed_deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=10.00,
        help_text="The fixed amount each member contributes per cycle."
    )
    
    # Additional group configuration fields
    max_members = models.PositiveIntegerField(
        default=50,
        help_text="Maximum number of members allowed in this group"
    )
    
    cycle_duration_days = models.PositiveIntegerField(
        default=30,
        help_text="Duration of each cycle in days"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Status fields
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_group_type_display()})"
    
    def clean(self):
        """Validate group data"""
        if self.fixed_deposit_amount <= 0:
            raise ValidationError("Fixed deposit amount must be greater than 0")
        
        if self.max_members > 9999:
            raise ValidationError("Maximum members cannot exceed 9999")
    
    @property
    def active_members_count(self):
        return self.members.filter(status='ACTIVE').count()
    
    @property
    def total_monthly_pot(self):
        """Calculate total monthly pot based on active members"""
        active_count = self.active_members_count
        return active_count * self.fixed_deposit_amount if active_count > 0 else 0

class Cycle(models.Model):
    """Represents a savings cycle within a group"""
    group = models.ForeignKey(
        SavingsGroup,
        on_delete=models.CASCADE,
        related_name='cycles'
    )
    
    cycle_number = models.PositiveIntegerField(
        help_text="The sequential number of this cycle (e.g., 1, 2, 3...)"
    )
    
    pot_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Total amount collected in this cycle"
    )
    
    # Status of the cycle
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PLANNED'
    )
    
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    actual_end_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        # Ensures that for a specific group, the cycle_number is unique
        unique_together = ('group', 'cycle_number')
        ordering = ['group', 'cycle_number']
    
    def __str__(self):
        return f"{self.group.name} - Cycle {self.cycle_number} ({self.status})"
    
    def save(self, *args, **kwargs):
        """Auto-calculate pot_total when saving"""
        if not self.pot_total and self.status == 'ACTIVE':
            self.pot_total = self.group.total_monthly_pot
        super().save(*args, **kwargs)

class DigitalBook(models.Model):
    """Digital ledger book for a member"""
    book_number = models.PositiveIntegerField(
        default=1,
        help_text="The sequential number for this ledger book.",
        unique=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Digital Book #{self.book_number}"
    
    def save(self, *args, **kwargs):
        """Auto-increment book_number if not provided"""
        if not self.book_number:
            last_book = DigitalBook.objects.order_by('-book_number').first()
            self.book_number = last_book.book_number + 1 if last_book else 1
        super().save(*args, **kwargs)

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
    
    # Connects Member to SavingsGroup
    group = models.ForeignKey(
        SavingsGroup,
        on_delete=models.CASCADE,
        related_name='members'
    )
    
    # Link to the DigitalBook 
    digital_book = models.OneToOneField(
        DigitalBook,
        on_delete=models.PROTECT,
        null=True, 
        blank=True,
        help_text="Digital ledger book assigned to this member"
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
    total_contributions = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_payouts = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Emergency contact info
    emergency_contact_name = models.CharField(max_length=255, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    
    class Meta:
        unique_together = ('user', 'group')
        ordering = ['payout_order', 'joined_at']
    
    def __str__(self):
        return f"{self.full_name} ({self.member_id}) - {self.group.name}"
    
    def save(self, *args, **kwargs):
        """Auto-generate member_id and assign digital book if needed"""
        # Generate member_id if not set
        if not self.member_id:
            self.member_id = generate_next_member_id(self.group)
        
        # Assign a digital book if not assigned and member is becoming active
        if not self.digital_book and self.status == 'ACTIVE':
            last_book = DigitalBook.objects.order_by('-book_number').first()
            new_book_number = last_book.book_number + 1 if last_book else 1
            self.digital_book = DigitalBook.objects.create(book_number=new_book_number)
        
        # Auto-assign payout_order if not set and group is rotating type
        if not self.payout_order and self.group.group_type == 'rotating':
            last_member = Member.objects.filter(group=self.group).exclude(payout_order=None).order_by('-payout_order').first()
            self.payout_order = (last_member.payout_order + 1) if last_member else 1
        
        super().save(*args, **kwargs)
    
    @property
    def net_balance(self):
        """Calculate member's net balance (contributions - payouts)"""
        return self.total_contributions - self.total_payouts
    
    @property
    def is_payment_current(self):
        """Check if member's payments are up to date"""
        if not self.last_contribution_date:
            return False
        
        # Logic to check if last contribution was within current cycle
        # You would need to implement this based on your cycle logic
        return True

class Contribution(models.Model):
    """Records individual contributions made by members"""
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    cycle = models.ForeignKey(
        Cycle,
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('CASH', 'Cash'),
            ('MPESA', 'M-Pesa'),
            ('BANK', 'Bank Transfer'),
            ('CARD', 'Card Payment'),
            ('OTHER', 'Other'),
        ],
        default='CASH'
    )
    transaction_reference = models.CharField(max_length=100, blank=True)
    contribution_date = models.DateTimeField(auto_now_add=True)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_contributions'
    )
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-contribution_date']
        indexes = [
            models.Index(fields=['member', 'cycle']),
            models.Index(fields=['contribution_date']),
        ]
    
    def __str__(self):
        return f"{self.member.full_name} - {self.amount} - Cycle {self.cycle.cycle_number}"

class Payout(models.Model):
    """Records payouts made to members"""
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='payouts'
    )
    cycle = models.ForeignKey(
        Cycle,
        on_delete=models.CASCADE,
        related_name='payouts'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('CASH', 'Cash'),
            ('MPESA', 'M-Pesa'),
            ('BANK', 'Bank Transfer'),
            ('CHEQUE', 'Cheque'),
            ('OTHER', 'Other'),
        ],
        default='CASH'
    )
    transaction_reference = models.CharField(max_length=100, blank=True)
    authorized_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='authorized_payouts'
    )
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-payout_date']
    
    def __str__(self):
        return f"Payout to {self.member.full_name} - {self.amount} - Cycle {self.cycle.cycle_number}"