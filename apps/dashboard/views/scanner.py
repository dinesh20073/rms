import json
import re
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Count, Q

from apps.tenants.models import Tenant
from apps.events.models import Event
from apps.registrations.models import Registration, Attendee, Customer
from apps.payments.models import Order
from apps.audit.models import AuditLog
from apps.notifications.services import send_checkin_success_email
from apps.dashboard.views.overview import get_current_tenant


def extract_clean_code(raw_input):
    """
    Cleans and extracts pass code from barcode strings, raw input, or full URLs.
    Example: 'https://www.admin.nizhalcommunity.in/pass/PASS-34FF1F4036/' -> 'PASS-34FF1F4036'
             'PASS-34FF1F4036' -> 'PASS-34FF1F4036'
             'ORD-BC5253ED' -> 'ORD-BC5253ED'
    """
    if not raw_input:
        return ""
    code = str(raw_input).strip()
    
    # Strip URL formatting if scanned from QR containing web link
    if '://' in code or '/pass/' in code:
        # Match pattern /pass/<CODE>/
        match = re.search(r'/pass/([A-Za-z0-9\-_]+)', code)
        if match:
            return match.group(1).strip()
        parts = code.rstrip('/').split('/')
        for i, part in enumerate(parts):
            if part == 'pass' and i + 1 < len(parts):
                code = parts[i + 1]
                break
        else:
            code = parts[-1]

    # Remove query string and hashes
    code = code.split('?')[0].split('#')[0].strip()
    return code


def parse_attendees_and_gender(registration, ticket_count=1):
    """
    Extracts all attendee items, ages, genders, and calculates male/female counts.
    """
    responses = registration.form_responses or {}
    customer = registration.customer

    def to_proper_case(val):
        if not val or str(val).strip() in ('-', '', 'None'):
            return '-'
        return str(val).strip().title()

    attendee_list = []

    # Person 1 (Primary)
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
    })

    # Co-Attendees from structured list
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
                })

    # Individual numbered fields fallback (person_2_name, person_2_gender, etc.)
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
        })

    # Precise gender counting
    male_count = 0
    female_count = 0
    other_count = 0

    for a in attendee_list:
        g = str(a.get('gender', '')).lower()
        if 'female' in g or g in ('f', 'female', 'woman', 'girl'):
            female_count += 1
        elif 'male' in g or g in ('m', 'male', 'man', 'boy'):
            male_count += 1
        else:
            other_count += 1

    return attendee_list, male_count, female_count, other_count


@login_required(login_url='login')
def scanner_page_view(request):
    """
    Renders the dedicated QR Scanner & Check-in Verification console.
    """
    tenant = get_current_tenant(request)
    events = Event.objects.filter(tenant=tenant).order_by('-event_start_date', '-created_at')
    
    selected_event_id = request.GET.get('event_id')
    selected_event = None
    if selected_event_id and selected_event_id.isdigit():
        selected_event = Event.objects.filter(id=int(selected_event_id), tenant=tenant).first()
    
    # If no event explicitly selected, select the most relevant event (first upcoming or most recent)
    if not selected_event and events.exists():
        selected_event = events.first()

    context = {
        'events': events,
        'selected_event': selected_event,
        'page_title': 'Ticket QR Scanner & Verification',
    }
    return render(request, 'dashboard/scanner/index.html', context)


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def scanner_verify_api(request):
    """
    API endpoint called when a QR code or Pass ID is scanned or entered.
    Verifies ticket authenticity, counts male/female attendees, records check-in timestamp,
    and sends gratitude participation email.
    """
    tenant = get_current_tenant(request)
    
    if request.method == 'POST':
        try:
            body = json.loads(request.body.decode('utf-8'))
            raw_code = body.get('code') or body.get('pass_code') or ''
            event_id = body.get('event_id')
            force_checkin = body.get('force', False)
        except Exception:
            raw_code = request.POST.get('code') or request.POST.get('pass_code') or ''
            event_id = request.POST.get('event_id')
            force_checkin = request.POST.get('force') in ('1', 'true', 'True')
    else:
        raw_code = request.GET.get('code') or request.GET.get('pass_code') or ''
        event_id = request.GET.get('event_id')
        force_checkin = request.GET.get('force') in ('1', 'true', 'True')

    clean_code = extract_clean_code(raw_code)
    if not clean_code:
        return JsonResponse({
            'success': False,
            'status': 'EMPTY',
            'message': 'Please provide a valid Pass ID, Order ID, or scan a ticket QR code.'
        }, status=400)

    # Resilient lookup: Pass Code -> Registration Code -> Order Code
    attendee = Attendee.objects.filter(pass_code=clean_code).first()
    registration = None

    if not attendee:
        registration = Registration.objects.filter(registration_code=clean_code).first()
        if not registration:
            order = Order.objects.filter(order_code=clean_code).first()
            if order:
                registration = order.registration

        if registration:
            attendee, _ = Attendee.objects.get_or_create(registration=registration)

    if not attendee:
        return JsonResponse({
            'success': False,
            'status': 'INVALID',
            'message': f"Ticket '{clean_code}' not found in database. Invalid or unissued pass.",
            'code': clean_code
        })

    registration = attendee.registration
    event = registration.event
    customer = registration.customer

    # Tenant check
    if event.tenant != tenant:
        return JsonResponse({
            'success': False,
            'status': 'WRONG_TENANT',
            'message': 'This ticket belongs to another organization account.',
            'code': clean_code
        })

    # Event match check (if user is currently filtered on a specific event)
    is_event_mismatch = False
    if event_id and str(event_id).isdigit():
        if event.id != int(event_id):
            is_event_mismatch = True

    # Registration status check
    if registration.status != 'COMPLETED':
        return JsonResponse({
            'success': False,
            'status': 'PAYMENT_PENDING',
            'message': f"Payment proof verification is pending ({registration.status}). Pass not yet validated for entry.",
            'code': clean_code,
            'event_title': event.title,
            'customer_name': customer.name,
            'customer_email': customer.email,
            'registration_status': registration.status,
            'amount': float(registration.amount),
        })

    # Compute ticket count & male / female breakdown
    raw_tc = registration.form_responses.get('Ticket Count') or registration.form_responses.get('ticket_count') or 1
    try:
        ticket_count = int(raw_tc)
    except (ValueError, TypeError):
        ticket_count = 1

    attendee_list, male_count, female_count, other_count = parse_attendees_and_gender(
        registration, ticket_count=max(ticket_count, 1)
    )
    total_spots = max(ticket_count, len(attendee_list))

    already_checked_in = attendee.is_checked_in
    checkin_timestamp_str = (
        timezone.localtime(attendee.checked_in_at).strftime('%d %b %Y, %I:%M %p')
        if attendee.checked_in_at
        else 'Earlier today'
    )

    email_sent = False
    email_error = None

    if already_checked_in and not force_checkin:
        # Duplicate entry detection
        return JsonResponse({
            'success': True,
            'status': 'ALREADY_CHECKED_IN',
            'message': f"⚠️ DUPLICATE ENTRY: Pass was already checked in at {checkin_timestamp_str}!",
            'is_duplicate': True,
            'is_mismatch': is_event_mismatch,
            'checked_in_at': checkin_timestamp_str,
            'code': attendee.pass_code,
            'event_title': event.title,
            'event_date': event.event_start_date.strftime('%d %b %Y, %I:%M %p') if event.event_start_date else 'TBD',
            'event_venue': event.venue or 'TBD',
            'customer_name': customer.name,
            'customer_email': customer.email,
            'customer_phone': customer.phone or '-',
            'total_spots': total_spots,
            'male_count': male_count,
            'female_count': female_count,
            'other_count': other_count,
            'amount_paid': float(registration.amount),
            'attendee_list': attendee_list,
        })

    # Perform check-in (mark checked in)
    now = timezone.now()
    attendee.is_checked_in = True
    attendee.checked_in_at = now
    attendee.save()

    # Log audit trail
    try:
        AuditLog.objects.create(
            tenant=tenant,
            action='ATTENDEE_CHECKIN',
            reference_id=attendee.pass_code,
            details={
                'attendee_name': customer.name,
                'email': customer.email,
                'event_title': event.title,
                'total_spots': total_spots,
                'male_count': male_count,
                'female_count': female_count,
                'scanned_by': request.user.username if request.user.is_authenticated else 'Staff',
            },
            actor=request.user.username if request.user.is_authenticated else 'Staff'
        )
    except Exception:
        pass

    # Send participation gratitude email
    try:
        email_log = send_checkin_success_email(attendee)
        email_sent = email_log.status in ('SENT', 'SIMULATED')
    except Exception as e:
        email_sent = False
        email_error = str(e)

    local_now_str = timezone.localtime(now).strftime('%d %b %Y, %I:%M %p')

    return JsonResponse({
        'success': True,
        'status': 'VERIFIED',
        'message': '✅ VALID TICKET - ENTRY CONFIRMED!',
        'is_duplicate': False,
        'is_mismatch': is_event_mismatch,
        'checked_in_at': local_now_str,
        'code': attendee.pass_code,
        'event_title': event.title,
        'event_date': event.event_start_date.strftime('%d %b %Y, %I:%M %p') if event.event_start_date else 'TBD',
        'event_venue': event.venue or 'TBD',
        'customer_name': customer.name,
        'customer_email': customer.email,
        'customer_phone': customer.phone or '-',
        'total_spots': total_spots,
        'male_count': male_count,
        'female_count': female_count,
        'other_count': other_count,
        'amount_paid': float(registration.amount),
        'attendee_list': attendee_list,
        'email_sent': email_sent,
        'email_error': email_error,
    })


@login_required(login_url='login')
def scanner_stats_api(request):
    """
    Returns live check-in stats for the selected event or all events of the tenant.
    """
    tenant = get_current_tenant(request)
    event_id = request.GET.get('event_id')

    attendees_qs = Attendee.objects.filter(registration__event__tenant=tenant, registration__status='COMPLETED')
    if event_id and str(event_id).isdigit():
        attendees_qs = attendees_qs.filter(registration__event_id=int(event_id))

    total_registered = attendees_qs.count()
    checked_in_qs = attendees_qs.filter(is_checked_in=True)
    total_checked_in = checked_in_qs.count()

    # Calculate male, female, total tickets across all checked-in attendees
    total_tickets = 0
    total_male = 0
    total_female = 0

    for att in checked_in_qs.select_related('registration', 'registration__customer')[:500]:
        responses = att.registration.form_responses or {}
        raw_tc = responses.get('Ticket Count') or responses.get('ticket_count') or 1
        try:
            tc = int(raw_tc)
        except (ValueError, TypeError):
            tc = 1
        _, m, f, _ = parse_attendees_and_gender(att.registration, ticket_count=max(tc, 1))
        total_tickets += max(tc, m + f)
        total_male += m
        total_female += f

    return JsonResponse({
        'total_registered': total_registered,
        'total_checked_in': total_checked_in,
        'total_tickets': total_tickets,
        'total_male': total_male,
        'total_female': total_female,
        'remaining': max(total_registered - total_checked_in, 0)
    })


@login_required(login_url='login')
@require_http_methods(['POST', 'GET'])
def scanner_resend_email_api(request, pass_code):
    """
    Allows staff to manually resend participation confirmation email from the scanner page.
    """
    tenant = get_current_tenant(request)
    attendee = Attendee.objects.filter(pass_code=pass_code, registration__event__tenant=tenant).first()
    if not attendee:
        return JsonResponse({'success': False, 'message': 'Attendee not found.'}, status=404)

    try:
        email_log = send_checkin_success_email(attendee)
        return JsonResponse({
            'success': True,
            'message': f"Participation email sent to {attendee.registration.customer.email} ✓",
            'status': email_log.status
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Failed to send email: {str(e)}"}, status=500)
