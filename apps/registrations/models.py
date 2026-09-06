import uuid
from django.db import models
from django.utils import timezone
from apps.tenants.models import Tenant
from apps.events.models import Event

class Customer(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='customers')
    name = models.CharField(max_length=255)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=50, blank=True)
    company = models.CharField(max_length=255, blank=True)
    designation = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} <{self.email}>"

class Registration(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Payment'),
        ('PROCESSING', 'Registration Processing'),
        ('COMPLETED', 'Registration Successful'),
        ('FAILED', 'Registration Failed'),
        ('MANUAL_REVIEW', 'Manual Review Needed'),
    ]

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='registrations')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='registrations')
    registration_code = models.CharField(max_length=50, unique=True, db_index=True)
    form_responses = models.JSONField(default=dict, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.registration_code} - {self.customer.name} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.registration_code:
            count = Registration.objects.count() + 1
            self.registration_code = f"REG-{count:06d}"
        super().save(*args, **kwargs)

class Attendee(models.Model):
    registration = models.OneToOneField(Registration, on_delete=models.CASCADE, related_name='attendee_pass')
    pass_code = models.CharField(max_length=64, unique=True)
    badge_number = models.CharField(max_length=30, blank=True)
    is_checked_in = models.BooleanField(default=False)
    checked_in_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.pass_code:
            self.pass_code = f"PASS-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Attendee {self.registration.customer.name} ({self.pass_code})"
