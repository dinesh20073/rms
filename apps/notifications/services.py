import io
import os
import base64
import qrcode
from django.core.mail import EmailMultiAlternatives, send_mail
from django.conf import settings
from django.template.loader import render_to_string
from apps.notifications.models import EmailLog
from apps.audit.services import log_audit_event

# Direct permanent public HTTPS URL for the Nizhal Event Banner (no attachments)
BANNER_WEB_URL = "https://iili.io/ndZzewv.png"

def get_attendee_qr_web_url(pass_code):
    """Returns direct public HTTPS URL for the QR code image."""
    return f"https://api.qrserver.com/v1/create-qr-code/?size=120x120&data={pass_code}&margin=1"

def generate_attendee_qr_bytes(pass_code):
    """Generates raw PNG bytes for the individual attendee pass QR code."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=1,
    )
    qr.add_data(pass_code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff").convert('RGB')
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return buffer.getvalue()

def generate_attendee_qr_base64(pass_code):
    """Generates an embedded PNG Base64 data URI for the individual's attendee pass QR code."""
    raw_bytes = generate_attendee_qr_bytes(pass_code)
    return base64.b64encode(raw_bytes).decode('utf-8')

def get_banner_base64():
    """Returns Base64 string of email-optimized Nizhal banner for local dashboard preview."""
    banner_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'nizhal_banner_email.jpg')
    if not os.path.exists(banner_path):
        banner_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'nizhal_banner_image.png')
    if os.path.exists(banner_path):
        with open(banner_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    return ''

def send_registration_success_email(registration):
    """
    Sends confirmation email with images loading directly from the web (zero email attachments).
    Logs email record in EmailLog for admin review and simulator preview.
    """
    from apps.registrations.models import Attendee
    
    customer = registration.customer
    event = registration.event
    order = getattr(registration, 'order', None)
    attendee = getattr(registration, 'attendee_pass', None)
    if not attendee:
        attendee, _ = Attendee.objects.get_or_create(registration=registration)

    pass_code = attendee.pass_code if attendee else (order.order_code if order else "PASS-CONFIRMED")
    
    banner_url = BANNER_WEB_URL
    qr_url = get_attendee_qr_web_url(pass_code)

    responses = registration.form_responses or {}
    def to_proper_case(val):
        if not val or str(val).strip() in ('-', '', 'None'):
            return '-'
        return str(val).strip().title()

    raw_tc = responses.get('Ticket Count') or responses.get('ticket_count') or 1
    try:
        ticket_count = int(raw_tc)
    except (ValueError, TypeError):
        ticket_count = 1

    if event and event.registration_fee is not None:
        unit_fee = float(event.registration_fee)
    elif ticket_count > 0:
        unit_fee = float(registration.amount) / ticket_count
    else:
        unit_fee = float(registration.amount)

    attendee_list = []
    p1_age = responses.get('Age') or responses.get('age') or responses.get('Age Category') or responses.get('age_category') or '-'
    p1_gender = to_proper_case(responses.get('Gender') or responses.get('gender') or '-')
    p1_name = f"{to_proper_case(customer.name)} (Primary)"
    attendee_list.append({
        'index': 1,
        'name': p1_name,
        'age': p1_age,
        'gender': p1_gender,
        'type': 'Primary Attendee',
        'email': customer.email,
        'phone': customer.phone,
        'amount': unit_fee,
    })

    co_list = (
        responses.get('Co-Attendees (Person 2 to N)')
        or responses.get('co_attendees')
        or responses.get('co_attendee_list')
        or []
    )
    if isinstance(co_list, list):
        for idx, item in enumerate(co_list, start=2):
            if isinstance(item, dict):
                c_name = to_proper_case(item.get('name') or item.get('full_name') or f"Attendee #{idx}")
                c_age = item.get('age') or item.get('age_category') or item.get('Age') or '-'
                c_gender = to_proper_case(item.get('gender') or item.get('Gender') or '-')
                attendee_list.append({
                    'index': idx,
                    'name': c_name,
                    'age': c_age,
                    'gender': c_gender,
                    'type': f'Co-Attendee #{idx}',
                    'email': '-',
                    'phone': '-',
                    'amount': unit_fee,
                })

    for idx in range(len(attendee_list) + 1, ticket_count + 1):
        raw_name = responses.get(f'person_{idx}_name') or f"Attendee #{idx}"
        c_name = to_proper_case(raw_name)
        c_age = responses.get(f'person_{idx}_age') or '-'
        c_gender = to_proper_case(responses.get(f'person_{idx}_gender') or '-')
        attendee_list.append({
            'index': idx,
            'name': c_name,
            'age': c_age,
            'gender': c_gender,
            'type': f'Co-Attendee #{idx}',
            'email': '-',
            'phone': '-',
            'amount': unit_fee,
        })

    subject = f"Registration Confirmed: {event.title} ({pass_code})"
    
    # Context with direct Web URLs (zero attachments)
    email_context = {
        'registration': registration,
        'customer': customer,
        'event': event,
        'order': order,
        'attendee': attendee,
        'pass_code': pass_code,
        'banner_src': banner_url,
        'qr_src': qr_url,
        'attendee_list': attendee_list,
        'ticket_count': max(ticket_count, len(attendee_list)),
        'unit_fee': unit_fee,
    }
    email_html = render_to_string('emails/registration_confirmed.html', email_context)

    status = 'SENT'
    error_msg = ''
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=f"Hi {customer.name}, Your registration {registration.registration_code} for {event.title} is confirmed!",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[customer.email]
        )
        msg.attach_alternative(email_html, "text/html")
        msg.send(fail_silently=False)
    except Exception as e:
        status = 'FAILED'
        error_msg = str(e)

    email_log = EmailLog.objects.create(
        tenant=event.tenant,
        recipient_email=customer.email,
        recipient_name=customer.name,
        subject=subject,
        body_html=email_html,
        event_type='REGISTRATION_COMPLETED',
        status=status,
        error_message=error_msg
    )

    log_audit_event(
        action='EMAIL_SENT',
        reference_id=registration.registration_code,
        details={'recipient': customer.email, 'subject': subject, 'email_log_id': email_log.id, 'status': status},
        tenant=event.tenant,
        actor='Nizhal Community'
    )
    return email_log

def send_payment_reminder_email(registration):
    """
    Sends payment reminder email with web-hosted banner (zero attachments).
    """
    customer = registration.customer
    event = registration.event
    order = getattr(registration, 'order', None)

    subject = f"Payment Reminder: Complete your booking for {event.title}"
    
    email_context = {
        'registration': registration,
        'customer': customer,
        'event': event,
        'order': order,
        'banner_src': BANNER_WEB_URL,
    }
    email_html = render_to_string('emails/payment_reminder.html', email_context)

    status = 'SENT'
    error_msg = ''
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=f"Hi {customer.name}, Complete your UPI payment for {event.title}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[customer.email]
        )
        msg.attach_alternative(email_html, "text/html")
        msg.send(fail_silently=False)
    except Exception as e:
        status = 'FAILED'
        error_msg = str(e)

    return EmailLog.objects.create(
        tenant=event.tenant,
        recipient_email=customer.email,
        recipient_name=customer.name,
        subject=subject,
        body_html=email_html,
        event_type='PAYMENT_REMINDER',
        status=status,
        error_message=error_msg
    )

def send_payment_under_review_email(registration):
    """
    Sends payment proof received / under review email with web-hosted banner (zero attachments).
    """
    customer = registration.customer
    event = registration.event
    order = getattr(registration, 'order', None)

    subject = f"Payment Proof Received: {event.title}"
    
    email_context = {
        'registration': registration,
        'customer': customer,
        'event': event,
        'order': order,
        'banner_src': BANNER_WEB_URL,
    }
    email_html = render_to_string('emails/payment_under_review.html', email_context)

    status = 'SENT'
    error_msg = ''
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=f"Hi {customer.name}, We have received your payment proof for {event.title}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[customer.email]
        )
        msg.attach_alternative(email_html, "text/html")
        msg.send(fail_silently=False)
    except Exception as e:
        status = 'FAILED'
        error_msg = str(e)

    return EmailLog.objects.create(
        tenant=event.tenant,
        recipient_email=customer.email,
        recipient_name=customer.name,
        subject=subject,
        body_html=email_html,
        event_type='PAYMENT_PROOF_SUBMITTED',
        status=status,
        error_message=error_msg
    )
