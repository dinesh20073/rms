import io
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
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_code} - ₹{self.amount} ({self.status})"

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
        # Generate dynamic standard UPI Intent URI with comment: Event Name - Person Name
        # Format: upi://pay?pa={upi_id}&pn={upi_name}&am={amount}&cu=INR&tn={Event - Name}
        params = {
            'pa': event.upi_id,
            'pn': event.upi_name,
            'am': f"{self.amount:.2f}",
            'cu': self.currency,
            'tn': f"{event.title} - {primary_name}"[:80]
        }
        self.upi_intent_url = f"upi://pay?{urllib.parse.urlencode(params)}"
        
        super().save(*args, **kwargs)

        # Generate QR code if not present
        if not self.qr_code_image and self.upi_intent_url:
            self.generate_qr_code()

    def generate_qr_code(self):
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
        filename = f"qr_{self.order_code}.png"
        self.qr_code_image.save(filename, ContentFile(buffer.getvalue()), save=False)
        Order.objects.filter(pk=self.pk).update(qr_code_image=self.qr_code_image)

    @property
    def gpay_intent(self):
        return self.upi_intent_url.replace("upi://", "gpay://upi/")

    @property
    def phonepe_intent(self):
        return self.upi_intent_url.replace("upi://", "phonepe://")

    @property
    def paytm_intent(self):
        return self.upi_intent_url.replace("upi://", "paytmmp://")

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
