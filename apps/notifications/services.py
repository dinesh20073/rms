import io
import base64
import qrcode
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from apps.notifications.models import EmailLog
from apps.audit.services import log_audit_event

def generate_attendee_qr_base64(pass_code):
    """Generates an embedded PNG Base64 data URI for the individual's attendee pass QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=1,
    )
    qr.add_data(pass_code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def send_registration_success_email(registration):
    """
    Sends confirmation email with individual attendee QR code image and ticket details.
    Logs email record in EmailLog for admin review and simulator preview.
    """
    customer = registration.customer
    event = registration.event
    order = getattr(registration, 'order', None)
    attendee = getattr(registration, 'attendee_pass', None)

    pass_code = attendee.pass_code if attendee else (order.order_code if order else "PASS-CONFIRMED")
    qr_base64 = generate_attendee_qr_base64(pass_code)

    subject = f"Registration Confirmed: {event.title} ({order.order_code if order else 'CONFIRMED'})"
    
    context = {
        'registration': registration,
        'customer': customer,
        'event': event,
        'order': order,
        'attendee': attendee,
        'pass_code': pass_code,
        'qr_base64': qr_base64,
    }
    
    body_html = render_to_string('emails/registration_confirmed.html', context)

    status = 'SENT'
    error_msg = ''
    try:
        send_mail(
            subject=subject,
            message=f"Hi {customer.name}, Your registration {registration.registration_code} for {event.title} is confirmed!",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer.email],
            html_message=body_html,
            fail_silently=True
        )
    except Exception as e:
        status = 'SIMULATED'
        error_msg = str(e)

    email_log = EmailLog.objects.create(
        tenant=event.tenant,
        recipient_email=customer.email,
        recipient_name=customer.name,
        subject=subject,
        body_html=body_html,
        event_type='REGISTRATION_COMPLETED',
        status=status,
        error_message=error_msg
    )

    log_audit_event(
        action='EMAIL_SENT',
        reference_id=registration.registration_code,
        details={'recipient': customer.email, 'subject': subject, 'email_log_id': email_log.id},
        tenant=event.tenant,
        actor='Google EMS Mailer'
    )
    return email_log

def send_payment_reminder_email(registration):
    """
    Sends payment reminder email for pending orders.
    """
    customer = registration.customer
    event = registration.event
    order = getattr(registration, 'order', None)

    subject = f"Payment Reminder: Complete your booking for {event.title}"
    
    context = {
        'registration': registration,
        'customer': customer,
        'event': event,
        'order': order,
    }
    
    body_html = render_to_string('emails/payment_reminder.html', context)

    status = 'SENT'
    error_msg = ''
    try:
        send_mail(
            subject=subject,
            message=f"Hi {customer.name}, Complete your UPI payment for {event.title}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer.email],
            html_message=body_html,
            fail_silently=True
        )
    except Exception as e:
        status = 'SIMULATED'
        error_msg = str(e)

    return EmailLog.objects.create(
        tenant=event.tenant,
        recipient_email=customer.email,
        recipient_name=customer.name,
        subject=subject,
        body_html=body_html,
        event_type='PAYMENT_REMINDER',
        status=status,
        error_message=error_msg
    )
