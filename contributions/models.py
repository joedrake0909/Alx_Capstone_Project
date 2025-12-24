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

    





