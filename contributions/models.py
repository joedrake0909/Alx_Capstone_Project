from django.db import models, transaction
# Import models from the 'groups' app to establish the ForeignKey links
from django.db import models 
from decimal import Decimal

class Contribution(models.Model):
    # The member who made the payment. 
    # This ForeignKey links a contribution record to a specific Member profile.
    member = models.ForeignKey(
        'groups.Member',
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    
    # The cycle this payment is for. 
    # This links the payment to a specific round or payout event.
    cycle = models.ForeignKey(
        'groups.Cycle',
        on_delete=models.CASCADE,
        related_name='contributions'
    )
    
    #Denormalized group field speeds up group-based queries despite redundancy.
    group = models.ForeignKey(
        'groups.Group',
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
        'contributions.Page',
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

    def save(self, *args, **kwargs):
        # 1. If this is a new entry, find the previous entry for this member
        if not self.pk:
            previous_entry = Entry.objects.filter(
                member=self.member
            ).order_by('-date', '-row_number', '-id').first()

            # 2. Get the starting balance
            starting_balance = previous_entry.current_balance if previous_entry else 0

            # 3. Calculate the new balance correctly
            # (Starting Balance + what they put in - what they took out)
            self.current_balance = starting_balance + self.deposit_amount - self.withdrawal_amount
        
        super().save(*args, **kwargs)

    @classmethod
    @transaction.atomic
    def create_multiple_deposits(cls, member, page, date, total_amount, num_rows):
        """
        Create multiple deposit entries for the same amount across consecutive rows
        
        Args:
            member: The Member object
            page: The Page object
            date: Date for all entries
            total_amount: Total amount to deposit
            num_rows: Number of rows to split the amount into
        
        Returns:
            List of created Entry objects
        """
        if num_rows <= 0:
            raise ValueError("Number of rows must be greater than 0")
        
        # Calculate amount per row
        amount_per_row = Decimal(str(total_amount)) / Decimal(str(num_rows))
        
        # Get the last row number on this page
        last_entry = cls.objects.filter(page=page).order_by('-row_number').first()
        start_row = last_entry.row_number + 1 if last_entry else 1
        
        # Get the last balance for this member
        previous_entry = cls.objects.filter(
            member=member
        ).order_by('-date', '-row_number', '-id').first()
        starting_balance = previous_entry.current_balance if previous_entry else Decimal('0')
        
        # Create and save entries one by one (so save() method is called)
        entries = []
        current_balance = starting_balance
        
        for i in range(num_rows):
            entry = cls(
                page=page,
                member=member,
                date=date,
                row_number=start_row + i,
                deposit_amount=amount_per_row,
                withdrawal_amount=Decimal('0'),
                # We'll let save() calculate the balance
            )
            # Call save() which will calculate current_balance
            entry.save()
            entries.append(entry)
        
        return entries

    @classmethod
    @transaction.atomic
    def create_multiple_entries(cls, entries_data):
        """
        Create multiple entries with different amounts in one go
        
        Args:
            entries_data: List of dictionaries, each containing:
                - page: Page object
                - member: Member object
                - date: Date
                - row_number: Row number
                - deposit_amount: Deposit amount
                - withdrawal_amount: Withdrawal amount
        
        Returns:
            List of created Entry objects
        """
        entries = []
        
        # Group by member to calculate balances properly
        entries_by_member = {}
        for data in entries_data:
            member_id = data['member'].id
            if member_id not in entries_by_member:
                entries_by_member[member_id] = []
            entries_by_member[member_id].append(data)
        
        # Process each member separately
        for member_id, member_entries in entries_by_member.items():
            # Sort by date and row_number for proper balance calculation
            sorted_entries = sorted(member_entries, key=lambda x: (x['date'], x['row_number']))
            
            for data in sorted_entries:
                entry = cls(
                    page=data['page'],
                    member=data['member'],
                    date=data['date'],
                    row_number=data['row_number'],
                    deposit_amount=data.get('deposit_amount', Decimal('0')),
                    withdrawal_amount=data.get('withdrawal_amount', Decimal('0')),
                )
                # Call save() which will calculate current_balance
                entry.save()
                entries.append(entry)
        
        return entries