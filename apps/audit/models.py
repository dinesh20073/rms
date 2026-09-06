from django.db import models
from apps.tenants.models import Tenant

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('REGISTRATION_CREATED', 'Registration Created'),
        ('PAYMENT_SESSION_CREATED', 'Payment Session Created'),
        ('UPI_INTENT_GENERATED', 'UPI Intent Generated'),
        ('PAYMENT_PROOF_UPLOADED', 'Payment Proof Uploaded'),
        ('OCR_STARTED', 'OCR Started'),
        ('OCR_COMPLETED', 'OCR Completed'),
        ('AMOUNT_MATCHED', 'Amount Matched'),
        ('TRANSACTION_ID_MATCHED', 'Transaction ID Matched'),
        ('PAYMENT_AUTO_VERIFIED', 'Payment Auto Verified'),
        ('PAYMENT_MANUAL_REVIEW', 'Payment Flagged for Manual Review'),
        ('PAYMENT_MANUAL_APPROVED', 'Payment Manually Approved'),
        ('PAYMENT_REJECTED', 'Payment Rejected'),
        ('REGISTRATION_STARTED', 'Registration Started'),
        ('REGISTRATION_SUCCESS', 'Registration Completed Successfully'),
        ('EMAIL_SENT', 'Email Sent'),
        ('PARTNER_API_CALL', 'Partner API Call'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='audit_logs', null=True, blank=True)
    actor = models.CharField(max_length=255, default='System')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES, db_index=True)
    reference_id = models.CharField(max_length=100, blank=True, db_index=True, help_text="e.g. REG-000123 or ORD-000123")
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.action} ({self.reference_id})"
