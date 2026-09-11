import io
import base64
import urllib.parse
from decimal import Decimal
import qrcode
from django.db import models
from django.core.files.base import ContentFile
from django.utils import timezone
from apps.registrations.models import Registration

class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Payment'),
        ('UPLOADED', 'Proof Uploaded'),
        ('VERIFYING', 'Verifying Payment'),
        ('VERIFIED', 'Payment Verified'),
        ('FAILED', 'Payment Failed'),
        ('MANUAL_REVIEW', 'Manual Review Required'),
    ]

    order_code = models.CharField(max_length=50, unique=True, db_index=True)
    registration = models.OneToOneField(Registration, on_delete=models.CASCADE, related_name='order')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    upi_intent_url = models.TextField(blank=True)
    qr_code_image = models.ImageField(upload_to='qrcodes/%Y/%m/', blank=True, null=True)
    qr_code_base64 = models.TextField(blank=True, default='', help_text="Permanent Base64 QR Image stored in DB")
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_code} - ₹{self.amount} ({self.status})"

    @property
    def qr_display_url(self):
        """Returns the embedded Base64 data URI or file URL or dynamic QR API fallback."""
        if self.qr_code_base64:
            return self.qr_code_base64
        if self.qr_code_image:
            try:
                return self.qr_code_image.url
            except Exception:
                pass
        if self.upi_intent_url:
            return f"https://api.qrserver.com/v1/create-qr-code/?size=250x250&data={urllib.parse.quote(self.upi_intent_url)}"
        return ''

    def save(self, *args, **kwargs):
        if not self.order_code:
            import secrets
            while True:
                candidate = f"ORD-{secrets.token_hex(4).upper()}"
                if not Order.objects.filter(order_code=candidate).exists():
                    self.order_code = candidate
                    break
            
        event = self.registration.event
        primary_name = self.registration.customer.name if self.registration and self.registration.customer else "Attendee"
        # Format: upi://pay?pa={upi_id}&pn={upi_name}&tr={order_code}&tn={comment}&comment={comment}&am={amount}&cu=INR
        clean_title = event.title.replace('&', 'and').strip()
        clean_comment = f"{self.order_code} - {clean_title}"
        params = {
            'pa': event.upi_id.strip(),
            'pn': event.upi_name.strip(),
            'tr': self.order_code,
            'tn': clean_comment,
            'comment': clean_comment,
            'am': f"{self.amount:.2f}",
            'cu': self.currency,
        }
        self.upi_intent_url = f"upi://pay?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote, safe='@')}"
        
        super().save(*args, **kwargs)

        # Generate QR code if not present
        if (not self.qr_code_base64 and not self.qr_code_image) and self.upi_intent_url:
            self.generate_qr_code()

    def generate_qr_code(self):
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=8,
                border=2,
            )
            qr.add_data(self.upi_intent_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#1E293B", back_color="white")
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            raw_bytes = buffer.getvalue()
            b64_str = base64.b64encode(raw_bytes).decode('utf-8')
            self.qr_code_base64 = f"data:image/png;base64,{b64_str}"

            filename = f"qr_{self.order_code}.png"
            self.qr_code_image.save(filename, ContentFile(raw_bytes), save=False)
            Order.objects.filter(pk=self.pk).update(qr_code_image=self.qr_code_image, qr_code_base64=self.qr_code_base64)
        except Exception:
            pass

    @property
    def gpay_intent(self):
        return self.upi_intent_url.replace("upi://pay", "tez://upi/pay")

    @property
    def phonepe_intent(self):
        return self.upi_intent_url.replace("upi://", "phonepe://")

    @property
    def paytm_intent(self):
        return self.upi_intent_url.replace("upi://", "paytmmp://")

    @property
    def bhim_intent(self):
        return self.upi_intent_url.replace("upi://", "bhim://")

    @property
    def payment_comment(self):
        if not self.registration or not self.registration.event:
            return f"Order {self.order_code}"
        event = self.registration.event
        clean_title = event.title.replace('&', 'and').strip()
        return f"{self.order_code} - {clean_title}"

    @property
    def whatsapp_intent(self):
        return self.upi_intent_url


class Payment(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    transaction_id = models.CharField(max_length=100, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    payer_name = models.CharField(max_length=255, blank=True)
    payer_upi = models.CharField(max_length=100, blank=True)
    payee_upi = models.CharField(max_length=100, blank=True)
    payment_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, default='SUCCESS')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment ₹{self.amount} (Txn: {self.transaction_id})"
