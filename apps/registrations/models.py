import uuid
import secrets
import string
from django.db import models
from django.utils import timezone
from apps.tenants.models import Tenant
from apps.events.models import Event

def generate_random_reg_id():
    """
    Generates a globally unique 9-character alphanumeric registration ID 
    separated into 3-character chunks with hyphens: XXX-XXX-XXX (e.g. 9A2-B7K-8F3).
    """
    alphabet = string.ascii_uppercase + string.digits
    p1 = ''.join(secrets.choice(alphabet) for _ in range(3))
    p2 = ''.join(secrets.choice(alphabet) for _ in range(3))
    p3 = ''.join(secrets.choice(alphabet) for _ in range(3))
    return f"{p1}-{p2}-{p3}"

class Customer(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='customers')
    reg_id = models.CharField(max_length=50, unique=True, db_index=True, blank=True, null=True, help_text="Permanent unique 9-char Reg ID (XXX-XXX-XXX) for individual")
    name = models.CharField(max_length=255)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=50, blank=True)
    company = models.CharField(max_length=255, blank=True)
    designation = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.reg_id or 'No Reg ID'}) <{self.email}>"

    def save(self, *args, **kwargs):
        if not self.reg_id:
            while True:
                candidate = generate_random_reg_id()
                if not Customer.objects.filter(reg_id=candidate).exists():
                    self.reg_id = candidate
                    break
        super().save(*args, **kwargs)

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
    registration_code = models.CharField(max_length=50, unique=True, db_index=True, help_text="Unique Reg ID (XXX-XXX-XXX)")
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
            if self.customer and self.customer.reg_id and not Registration.objects.filter(registration_code=self.customer.reg_id).exists():
                self.registration_code = self.customer.reg_id
            else:
                while True:
                    candidate = generate_random_reg_id()
                    if not Registration.objects.filter(registration_code=candidate).exists():
                        self.registration_code = candidate
                        break
        super().save(*args, **kwargs)

    @property
    def latest_email_log(self):
        from apps.notifications.models import EmailLog
        return EmailLog.objects.filter(
            recipient_email=self.customer.email,
            tenant=self.event.tenant
        ).order_by('-sent_at').first()

    @property
    def client_ip(self):
        if isinstance(self.form_responses, dict):
            return self.form_responses.get('_client_ip') or self.form_responses.get('client_ip') or '127.0.0.1'
        return '127.0.0.1'

    @property
    def client_device(self):
        if isinstance(self.form_responses, dict):
            device_label = self.form_responses.get('_client_device')
            if device_label:
                return device_label
            ua = self.form_responses.get('_client_ua') or ''
            if 'iPhone' in ua: return 'iPhone (iOS)'
            if 'iPad' in ua: return 'iPad (iPadOS)'
            if 'Android' in ua: return 'Android Mobile'
            if 'Windows' in ua: return 'Windows PC'
            if 'Macintosh' in ua: return 'Mac OS'
            if 'Linux' in ua: return 'Linux PC'
            return 'Web Browser'
        return 'Web Client'

    @property
    def is_confirmation_email_sent(self):
        from apps.notifications.models import EmailLog
        return EmailLog.objects.filter(
            recipient_email=self.customer.email,
            tenant=self.event.tenant,
            event_type='REGISTRATION_COMPLETED',
            status__in=['SENT', 'SIMULATED']
        ).exists()

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
