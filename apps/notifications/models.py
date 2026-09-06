from django.db import models
from apps.tenants.models import Tenant

class EmailLog(models.Model):
    STATUS_CHOICES = [
        ('SENT', 'Sent'),
        ('SIMULATED', 'Simulated (In-App)'),
        ('FAILED', 'Failed'),
    ]

    EVENT_TYPE_CHOICES = [
        ('REGISTRATION_CREATED', 'Registration Created'),
        ('PAYMENT_PROOF_RECEIVED', 'Payment Proof Received'),
        ('REGISTRATION_COMPLETED', 'Registration Completed / Confirmed'),
        ('PAYMENT_REJECTED', 'Payment Rejected'),
        ('MANUAL_REVIEW_ALERT', 'Manual Review Alert'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='email_logs', null=True, blank=True)
    recipient_email = models.EmailField(db_index=True)
    recipient_name = models.CharField(max_length=255, blank=True)
    subject = models.CharField(max_length=255)
    body_html = models.TextField()
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES, default='REGISTRATION_COMPLETED')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SENT')
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.subject} -> {self.recipient_email} ({self.status})"
