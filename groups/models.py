from django.db import models
from django.contrib.auth.models import User
import string
from django.core.exceptions import ValidationError
from django.utils import timezone

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

class Group(models.Model):
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
        help_text="The developer/partner who created this group",
        null=True,
        blank=True,
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
        'Group',
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
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('group', 'cycle_number')
        ordering = ['group', 'cycle_number']
    
    def __str__(self):
        return f"{self.group.name} - Cycle {self.cycle_number} ({self.status})"
    
    def save(self, *args, **kwargs):
        """Auto-calculate pot_total when saving"""
        if not self.pot_total and self.status == 'ACTIVE':
            self.pot_total = self.group.total_monthly_pot
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
    
    group = models.ForeignKey(
        'Group',
        on_delete=models.CASCADE,
        related_name='members'
    )

    joined_at = models.DateTimeField(auto_now_add=True)  # ✅ This is correct!
    
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
        return self.total_contributions - self.total_payouts
    
    @property
    def is_payment_current(self):
        """Check if member's payments are up to date"""
        if not self.last_contribution_date:
            return False
        
        # Logic to check if last contribution was within current cycle
        # You would need to implement this based on your cycle logic
        return True

class DigitalBook(models.Model):
    """Digital ledger book for a member - Following the requested structure"""
    member = models.ForeignKey('Member', on_delete=models.CASCADE, related_name='books')
    book_number = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('member', 'book_number')
        ordering = ['member', 'book_number']

    def __str__(self):
        return f"Book {self.book_number} for {self.member.full_name}"
    
    @property
    def total_pages(self):
        """Get total number of pages in this book"""
        return self.pages.count()
    
    @property
    def total_entries(self):
        """Get total number of entries in this book"""
        return Entry.objects.filter(page__digital_book=self).count()
    
    @property
    def book_balance(self):
        """Calculate the balance at the end of this book"""
        last_entry = Entry.objects.filter(page__digital_book=self).order_by('-page__page_number', '-row_number').first()
        return last_entry.current_balance if last_entry else 0

class Page(models.Model):
    """Page within a digital book - Following the requested structure"""
    digital_book = models.ForeignKey(DigitalBook, on_delete=models.CASCADE, related_name='pages')
    page_number = models.PositiveIntegerField()

    class Meta:
        unique_together = ('digital_book', 'page_number')
        ordering = ['digital_book', 'page_number']

    def __str__(self):
        return f"Page {self.page_number} - {self.digital_book}"
    
    @property
    def total_entries(self):
        """Get total number of entries on this page"""
        return self.entries.count()
    
    @property
    def is_full(self):
        """Check if this page is full (31 rows)"""
        return self.entries.count() >= 31

class Entry(models.Model):
    """Ledger entry on a specific page"""
    STATUS_CHOICES = [
        ('APPROVED', 'Approved'),
        ('PENDING', 'Pending'),
        ('REJECTED', 'Rejected'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('MPESA', 'M-Pesa'),
        ('BANK', 'Bank Transfer'),
        ('CARD', 'Card Payment'),
        ('OTHER', 'Other'),
    ]
    
    member = models.ForeignKey('Member', on_delete=models.CASCADE, related_name='entries')
    page = models.ForeignKey(Page, on_delete=models.CASCADE, related_name='entries')
    row_number = models.PositiveIntegerField()
    
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    withdrawal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    current_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    date = models.DateField(default=timezone.now)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='CASH')
    transaction_reference = models.CharField(max_length=100, blank=True)
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='APPROVED')
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_entries'
    )
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('page', 'row_number')
        ordering = ['page__digital_book__book_number', 'page__page_number', 'row_number']
        indexes = [
            models.Index(fields=['member', 'date']),
            models.Index(fields=['date']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        if self.deposit_amount > 0:
            return f"Deposit: {self.deposit_amount} - Row {self.row_number}"
        elif self.withdrawal_amount > 0:
            return f"Withdrawal: {self.withdrawal_amount} - Row {self.row_number}"
        else:
            return f"Entry - Row {self.row_number}"
    
    def clean(self):
        """Validate entry data"""
        if self.deposit_amount > 0 and self.withdrawal_amount > 0:
            raise ValidationError("An entry cannot have both deposit and withdrawal amounts.")
        
        if self.deposit_amount < 0 or self.withdrawal_amount < 0:
            raise ValidationError("Amounts cannot be negative.")
        
        if self.row_number < 1 or self.row_number > 31:
            raise ValidationError("Row number must be between 1 and 31.")
    
    @property
    def transaction_type(self):
        """Get the type of transaction"""
        if self.deposit_amount > 0:
            return 'DEPOSIT'
        elif self.withdrawal_amount > 0:
            return 'WITHDRAWAL'
        else:
            return 'ADJUSTMENT'
    
    @property
    def amount(self):
        """Get the transaction amount (positive for deposit, negative for withdrawal)"""
        if self.deposit_amount > 0:
            return self.deposit_amount
        elif self.withdrawal_amount > 0:
            return -self.withdrawal_amount
        else:
            return 0
        

    def save(self, *args, **kwargs):
        """🌟 EACH PAGE STARTS FROM ZERO LOGIC 🌟"""
        if not self.pk: # Only on creation
            # Find last entry ONLY on the SAME page
            last_entry = Entry.objects.filter(
                member=self.member,
                page=self.page
            ).order_by('-row_number').first()
            
            # If no entry on this page, prev_bal is 0
            prev_bal = last_entry.current_balance if last_entry else 0
            
            if self.deposit_amount > 0:
                self.current_balance = prev_bal + self.deposit_amount
            elif self.withdrawal_amount > 0:
                self.current_balance = prev_bal - self.withdrawal_amount
        
        super().save(*args, **kwargs)

class Payout(models.Model):
    """Records payouts made to members"""
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('MPESA', 'M-Pesa'),
        ('BANK', 'Bank Transfer'),
        ('CHEQUE', 'Cheque'),
        ('OTHER', 'Other'),
    ]
    
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='payouts'
    )
    
    cycle = models.ForeignKey(
        'Cycle',
        on_delete=models.CASCADE,
        related_name='payouts'
    )
    
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payout_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
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