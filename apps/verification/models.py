from django.db import models
from django.contrib.auth.models import User
from apps.payments.models import Order

class PaymentEvidence(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='evidence_records')
    screenshot = models.ImageField(upload_to='payment_proofs/%Y/%m/', blank=True, null=True)
    image_base64 = models.TextField(blank=True, help_text="Permanent Base64 Image data for Supabase/Serverless persistence")
    raw_ocr_text = models.TextField(blank=True)
    extracted_data = models.JSONField(default=dict, blank=True, help_text="Structured OCR attributes (amount, txn_id, date, payee)")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    @property
    def has_image(self):
        if self.screenshot:
            try:
                if self.screenshot.name:
                    return True
            except Exception:
                pass
        if self.image_base64 and self.image_base64.strip():
            return True
        return False

    @property
    def display_url(self):
        if not self.has_image:
            return ''
        if hasattr(self, 'order') and self.order and getattr(self.order, 'order_code', None):
            return f'/dashboard/verification/proof/{self.order.order_code}/'
        if self.screenshot:
            try:
                return self.screenshot.url
            except Exception:
                pass
        if self.image_base64:
            return self.image_base64
        return ''

    def save(self, *args, **kwargs):
        if self.screenshot and not self.image_base64:
            try:
                import base64
                file_obj = getattr(self.screenshot, 'file', self.screenshot)
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
                content = file_obj.read()
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
                if content:
                    b64 = base64.b64encode(content).decode('utf-8')
                    name = str(getattr(self.screenshot, 'name', '')).lower()
                    mime = 'image/png' if name.endswith('.png') else ('image/webp' if name.endswith('.webp') else 'image/jpeg')
                    self.image_base64 = f"data:{mime};base64,{b64}"
            except Exception:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Evidence for {self.order.order_code} ({self.uploaded_at.strftime('%Y-%m-%d %H:%M')})"


class Verification(models.Model):
    DECISION_CHOICES = [
        ('AUTO_VERIFIED', 'Auto Verified by AI/Rules'),
        ('MANUAL_APPROVED', 'Manually Approved'),
        ('MANUAL_REVIEW', 'Needs Manual Review'),
        ('REJECTED', 'Payment Rejected / Invalid'),
        ('PENDING', 'Pending Verification'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='verification')
    evidence = models.ForeignKey(PaymentEvidence, on_delete=models.SET_NULL, null=True, blank=True, related_name='verifications')
    decision = models.CharField(max_length=30, choices=DECISION_CHOICES, default='PENDING', db_index=True)
    
    # Rule Evaluation Results
    is_amount_matched = models.BooleanField(default=False)
    is_duplicate_txn = models.BooleanField(default=False)
    is_txn_id_found = models.BooleanField(default=False)
    is_payee_matched = models.BooleanField(default=False)
    
    ocr_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    ocr_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    ocr_payee = models.CharField(max_length=255, blank=True, null=True)
    ocr_timestamp_str = models.CharField(max_length=100, blank=True, null=True)
    
    review_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_verifications')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def has_proof_image(self):
        if self.evidence and getattr(self.evidence, 'has_image', False):
            return True
        if hasattr(self, 'order') and self.order and getattr(self.order, 'has_proof_image', False):
            return True
        return False

    def __str__(self):
        return f"Verification for {self.order.order_code} - {self.decision}"
