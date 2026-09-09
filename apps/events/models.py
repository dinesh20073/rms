import io
import urllib.parse
import qrcode
from django.db import models
from django.core.files.base import ContentFile
from django.utils.text import slugify
from django.utils import timezone
from apps.tenants.models import Tenant

class Event(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('ARCHIVED', 'Archived'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='events')
    event_code = models.CharField(max_length=50, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    
    # Financial / UPI configuration (Always INR)
    registration_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, default='INR', editable=False)
    upi_id = models.CharField(max_length=100, default='dinesh.b@superyes')
    upi_name = models.CharField(max_length=100, default='Dinesh')
    upi_qr_code = models.ImageField(upload_to='event_qrs/', blank=True, null=True)
    
    # Schedule & Capacity
    registration_opens = models.DateTimeField(default=timezone.now)
    registration_closes = models.DateTimeField(null=True, blank=True)
    event_start_date = models.DateTimeField(null=True, blank=True)
    venue = models.CharField(max_length=255, default='Online / Main Campus', blank=True)
    max_capacity = models.PositiveIntegerField(default=1000)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.event_code})"

    def generate_master_event_qr(self):
        """Generates the master UPI QR code for this event based on UPI ID and fixed fee."""
        params = {
            'pa': self.upi_id,
            'pn': self.upi_name,
            'cu': 'INR',
        }
        if self.registration_fee > 0:
            params['am'] = f"{self.registration_fee:.2f}"
            params['tn'] = f"{self.title} Entry Fee"[:60]
            
        upi_url = f"upi://pay?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote, safe='@')}"
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(upi_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#202124", back_color="white")
        
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        filename = f"event_qr_{self.event_code}.png"
        self.upi_qr_code.save(filename, ContentFile(buffer.getvalue()), save=False)

    def save(self, *args, **kwargs):
        self.currency = 'INR'  # Always INR

        if not self.slug:
            base_slug = slugify(self.title) or 'event'
            slug = base_slug
            counter = 1
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug

        if not self.event_code:
            year = timezone.now().year
            count = Event.objects.filter(event_code__startswith=f"EVT-{year}-").count() + 1
            self.event_code = f"EVT-{year}-{count:04d}"

        # If no QR code uploaded, generate master event QR
        if not self.upi_qr_code and self.upi_id:
            self.generate_master_event_qr()

        super().save(*args, **kwargs)

    @property
    def is_registration_open(self):
        now = timezone.now()
        if self.status != 'OPEN':
            return False
        if self.registration_opens and now < self.registration_opens:
            return False
        if self.registration_closes and now > self.registration_closes:
            return False
        if self.max_capacity and self.registrations.filter(status='COMPLETED').count() >= self.max_capacity:
            return False
        return True

    def get_registration_closed_reason(self):
        now = timezone.now()
        if self.status != 'OPEN':
            return {
                'code': 'CLOSED_MANUAL',
                'title': 'Registrations Closed',
                'message': 'The event organizer is currently not accepting new registrations.',
                'deadline': self.registration_closes,
            }
        if self.registration_opens and now < self.registration_opens:
            return {
                'code': 'NOT_STARTED',
                'title': 'Registration Opening Soon',
                'message': f"Registrations will officially open on {self.registration_opens.strftime('%d %b %Y at %I:%M %p')}.",
                'deadline': self.registration_opens,
            }
        if self.registration_closes and now > self.registration_closes:
            return {
                'code': 'DEADLINE_EXPIRED',
                'title': 'Registration Deadline Passed',
                'message': f"The deadline for registration ended on {self.registration_closes.strftime('%d %b %Y at %I:%M %p')}.",
                'deadline': self.registration_closes,
            }
        if self.max_capacity and self.registrations.filter(status='COMPLETED').count() >= self.max_capacity:
            return {
                'code': 'CAPACITY_REACHED',
                'title': 'Registration Full',
                'message': f"This event has reached its maximum attendee capacity ({self.max_capacity} attendees).",
                'deadline': self.registration_closes,
            }
        return None

