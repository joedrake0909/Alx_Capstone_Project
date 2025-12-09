from django.db import models
from django.contrib.auth.models import User

class Group(models.Model):
    name = models.CharField(max_length=100, unique=True)


    # A description of the group, its purpose, or rules
    description = models.TextField()

    # The agreed-upon amount to contribute per cycle
    contribution_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="The amount each memmber contributes per cycle."
    )

    admin = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='managed_grooup',
        help_text="The Django User designated as the Group Administrator."
    )


    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    
class Cycle(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='cycles'
    )

    pot_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
        help_text="Total amount collected in this cycle (N * contribution_amount)"
    )

    # Status of the cycle (e.g., 'Planning', 'Active', 'Completed')
    STATUS_CHOICES = [
        ('PLANNED', 'Planned'),
        ('ACTIVE', 'Active'),
        ('COMPLETED', 'Completed'),
    ]
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='PLANNED'
    )


    class Meta:
        # Ensures that for a specific group, the cycle_number is unique
        unique_together = ('group', 'cycle_number')
        # Order cycles sequentially
        ordering = ['group', 'cycle_number']

    def __str__(self):
        return f"{self.group.name} - Cycle {self.cycle_number}"


class Member(models.Model):
    #The OneToOneField creates a unique connection where each Django user account has exactly one corresponding member profile for login and profile management.
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='member_profile'
    )

    # Connects Member to Group, enabling group membership.
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='members'
    )  

    # Status of the member
    STATUS_CHOICES = [
        ('ACTIVE', 'Active')
        ('INACTIVE', 'Inactive'),
        ('PENDING', 'Pending '),
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
        unique=True,
        help_text="The sequence number for receiving the pot in the group."
    )

    # Optional: Date when the member joined the group
    joined_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.group.name}"
    
    class Meta:
        unique_together = ('user', 'group')










# Create your models here.
