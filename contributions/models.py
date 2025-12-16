from django.db import models
# Import models from the 'groups' app to establish the ForeignKey links
from groups.models import Member, Cycle, Group 

class Contribution(models.Model):
    # The member who made the payment. 
    # This ForeignKey links a contribution record to a specific Member profile.
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    
    # The cycle this payment is for. 
    # This links the payment to a specific round or payout event.
    cycle = models.ForeignKey(
        Cycle,
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    
    #Denormalized group field speeds up group-based queries despite redundancy.
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='all_contributions'
    )

    # The actual amount paid. 
    # This must be a DecimalField for precise monetary tracking.
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    # The date and time the contribution was recorded. 
    # auto_now_add=True records the moment of creation, essential for tracking time.
    paid_at = models.DateTimeField(auto_now_add=True)
    
    # Optional field to track the payment method (e.g., Bank Transfer, Cash, Mobile Money)
    PAYMENT_METHODS = [
        ('BANK', 'Bank Transfer'),
        ('CASH', 'Cash'),
        ('MOBILE', 'Mobile Money'),
        ('OTHER', 'Other'),
    ]
    payment_method = models.CharField(
        max_length=10,
        choices=PAYMENT_METHODS,
        default='BANK'
    )

    def __str__(self):
        return f"{self.member.user.username} paid {self.amount} for Cycle {self.cycle.cycle_number}"

    class Meta:
        # A crucial constraint: A single member can only contribute ONCE per cycle.
        # This prevents accidental or fraudulent duplicate payments for the same round.
        unique_together = ('member', 'cycle')

    
class Page(models.Model):
    digital_book = models.ForeignKey(
    "groups.DigitalBook",
    on_delete=models.CASCADE,
    related_name='pages'
 )
    page_number = models.PositiveIntegerField()

    class Meta:
        unique_together = ('digital_book', 'page_number')
        ordering = ['page_number']

    def __str__(self):
        return f"Book {self.digital_book.book_number}, Page {self.page_number}"
    

class Entry(models.Model):
    page = models.ForeignKey(
        Page,
        on_delete=models.CASCADE,
        related_name='entries'
    )

    member = models.ForeignKey(
        "groups.Member",
        on_delete=models.CASCADE,
        related_name='all_entries'
    )

    # Structure Field
    date = models.DateField()
    row_number = models.PositiveIntegerField(
        help_text="Transaction row number on the page"
    )

    # Financial fields
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    withdrawal_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Stored balance for that specific row (crucial for integrity check)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2)

    STATUS_CHOICES = [
        ('PENDING', 'Pending'), ('APPROVED', 'Approved'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')

    class Meta:
        # Ensures a page cannot have two entries with the same row number
        unique_together = ('page', 'row_number')
        ordering = ['date', 'row_number']

    def __str__(self):
        return f"E#{self.id} | {self.member.full_name}"