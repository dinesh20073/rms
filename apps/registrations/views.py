from django.shortcuts import render, get_object_or_404, redirect


def ai_innovators_register_view(request):
    """Render the custom AI Innovators Summit registration page.
    The form posts to the generic submit view which handles creation of
    Registration and Order objects.
    """
    # Ensure the event exists; replace slug with actual event slug.
    event = get_object_or_404(Event, slug='ai-innovators-2026')
    return render(request, 'public/ai_innovators_register.html', {'event': event})
from django.contrib import messages
from django.http import JsonResponse
from apps.events.models import Event
from apps.forms_builder.models import Form, FormField
from apps.registrations.models import Customer, Registration, Attendee
from apps.payments.models import Order
from apps.audit.services import log_audit_event

def public_registration_view(request, slug):
    event = get_object_or_404(Event, slug=slug)
    
    # Ensure form exists and has default fields
    form_obj, created = Form.objects.get_or_create(event=event)
    if created or not form_obj.fields.exists():
        form_obj.create_default_fields()

    fields = form_obj.fields.all()

    context = {
        'event': event,
        'form_obj': form_obj,
        'fields': fields,
    }
    return render(request, 'public/register.html', context)

def submit_registration_view(request, slug):
    if request.method != 'POST':
        return redirect('public-register', slug=slug)

    event = get_object_or_404(Event, slug=slug)
    form_obj = get_object_or_404(Form, event=event)
    fields = form_obj.fields.all()

    # Extract customer core fields
    name = request.POST.get('full_name', '').strip()
    email = request.POST.get('email_address', '').strip().lower()
    phone = request.POST.get('phone_number', '').strip()
    company = request.POST.get('company_organization', '').strip()
    designation = request.POST.get('designation_role', '').strip()

    # Collect custom responses
    form_responses = {}
    for f in fields:
        val = request.POST.get(f.field_key)
        if f.field_type == 'checkbox':
            val = request.POST.get(f.field_key) == 'on'
        form_responses[f.label] = val

        if f.is_required and not val:
            messages.error(request, f"Please fill in the required field: {f.label}")
            return redirect('public-register', slug=slug)

    if not name or not email:
        messages.error(request, "Name and Email are required.")
        return redirect('public-register', slug=slug)

    customer, _ = Customer.objects.get_or_create(
        tenant=event.tenant,
        email=email,
        defaults={
            'name': name,
            'phone': phone,
            'company': company,
            'designation': designation
        }
    )
    # Update latest details
    customer.name = name
    if phone: customer.phone = phone
    if company: customer.company = company
    if designation: customer.designation = designation
    customer.save()

    # Calculate ticket count & total amount
    ticket_count = 1
    for key, val in form_responses.items():
        if 'ticket' in str(key).lower():
            try:
                ticket_count = max(1, int(val))
            except (ValueError, TypeError):
                ticket_count = 1

    # Extract Co-Attendees (Person 2 to Person N)
    co_attendees = []
    if ticket_count > 1:
        for i in range(2, ticket_count + 1):
            p_name = request.POST.get(f'person_{i}_name', '').strip()
            p_age = request.POST.get(f'person_{i}_age', '').strip()
            p_gender = request.POST.get(f'person_{i}_gender', '').strip()
            if p_name:
                co_attendees.append({
                    'person_number': i,
                    'name': p_name,
                    'age_category': p_age,
                    'gender': p_gender
                })
        form_responses['Co-Attendees (Person 2 to N)'] = co_attendees

    total_amount = event.registration_fee * ticket_count

    if total_amount == 0:
        # Direct Instant Confirmation for Free Events
        registration = Registration.objects.create(
            event=event,
            customer=customer,
            amount=0,
            form_responses=form_responses,
            status='COMPLETED'
        )
        order = Order.objects.create(
            registration=registration,
            amount=0,
            currency=event.currency,
            status='VERIFIED'
        )
        attendee, _ = Attendee.objects.get_or_create(registration=registration)
        
        from apps.notifications.services import send_registration_success_email
        send_registration_success_email(registration)

        log_audit_event(
            'FREE_REGISTRATION_CONFIRMED',
            registration.registration_code,
            {'customer': email, 'event': event.title, 'pass_code': attendee.pass_code},
            tenant=event.tenant,
            actor=name
        )

        return redirect('attendee-badge', pass_code=attendee.pass_code)

    registration = Registration.objects.create(
        event=event,
        customer=customer,
        amount=total_amount,
        form_responses=form_responses,
        status='PENDING'
    )

    order = Order.objects.create(
        registration=registration,
        amount=total_amount,
        currency=event.currency,
        status='PENDING'
    )

    log_audit_event(
        'REGISTRATION_CREATED',
        registration.registration_code,
        {'customer': email, 'event': event.title, 'amount': str(registration.amount)},
        tenant=event.tenant,
        actor=name
    )

    log_audit_event(
        'PAYMENT_SESSION_CREATED',
        order.order_code,
        {'amount': str(order.amount), 'upi_id': event.upi_id},
        tenant=event.tenant,
        actor='EMS Payment Gateway'
    )

    return redirect('payment-checkout', order_code=order.order_code)

def registration_status_view(request, registration_code):
    registration = get_object_or_404(Registration, registration_code=registration_code)
    order = getattr(registration, 'order', None)
    if order:
        return redirect('payment-checkout', order_code=order.order_code)
    attendee = getattr(registration, 'attendee_pass', None)
    if attendee:
        return redirect('attendee-badge', pass_code=attendee.pass_code)
    return redirect('public-register', slug=registration.event.slug)

def attendee_badge_view(request, pass_code):
    from apps.notifications.services import generate_attendee_qr_base64
    from apps.payments.models import Order
    
    # Resilient lookup: pass_code -> registration_code -> order_code
    attendee = Attendee.objects.filter(pass_code=pass_code).first()
    if not attendee:
        reg = Registration.objects.filter(registration_code=pass_code).first()
        if not reg:
            order = Order.objects.filter(order_code=pass_code).first()
            if order:
                # If payment not verified, redirect to payment page
                if order.status != 'VERIFIED':
                    messages.info(request, "Your payment is being processed. Please wait for verification.")
                    return redirect('payment-checkout', order_code=order.order_code)
                reg = order.registration
        if reg:
            attendee, _ = Attendee.objects.get_or_create(registration=reg)
            
    if not attendee:
        return get_object_or_404(Attendee, pass_code=pass_code)

    registration = attendee.registration
    responses = registration.form_responses or {}
    customer = registration.customer
    event = registration.event

    # Helper for strict proper case
    def to_proper_case(val):
        if not val or str(val).strip() in ('-', '', 'None'):
            return '-'
        return str(val).strip().title()

    # Ticket count
    raw_tc = responses.get('Ticket Count') or responses.get('ticket_count') or 1
    try:
        ticket_count = int(raw_tc)
    except (ValueError, TypeError):
        ticket_count = 1

    # Single ticket fee
    if event and event.registration_fee is not None:
        unit_fee = float(event.registration_fee)
    elif ticket_count > 0:
        unit_fee = float(registration.amount) / ticket_count
    else:
        unit_fee = float(registration.amount)

    # Extract Person list (Person 1 + Person 2 to Person N)
    attendee_list = []

    # Person 1 (Primary Attendee)
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

    # Co-Attendees from structured list or individual fields
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

    # If ticket_count > len(attendee_list), fill remaining
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

    # Generate embedded Base64 QR code
    try:
        qr_base64 = generate_attendee_qr_base64(attendee.pass_code)
    except Exception:
        qr_base64 = None

    return render(request, 'public/attendee_pass.html', {
        'attendee': attendee,
        'registration': registration,
        'event': event,
        'customer': customer,
        'attendee_list': attendee_list,
        'ticket_count': max(ticket_count, len(attendee_list)),
        'unit_fee': unit_fee,
        'qr_base64': qr_base64,
    })

def send_pass_email_view(request, pass_code):
    from apps.notifications.services import send_registration_success_email
    from apps.payments.models import Order
    
    # Resilient lookup: pass_code -> registration_code -> order_code
    attendee = Attendee.objects.filter(pass_code=pass_code).first()
    if not attendee:
        reg = Registration.objects.filter(registration_code=pass_code).first()
        if not reg:
            order = Order.objects.filter(order_code=pass_code).first()
            if order:
                reg = order.registration
        if reg:
            attendee, _ = Attendee.objects.get_or_create(registration=reg)
            
    if not attendee:
        return JsonResponse({'success': False, 'error': 'Attendee pass not found.'}, status=404)
        
    registration = attendee.registration
    try:
        email_log = send_registration_success_email(registration)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json' or request.method == 'POST':
            return JsonResponse({
                'success': True,
                'email': registration.customer.email,
                'message': f"Official pass sent to {registration.customer.email}"
            })
        messages.success(request, f"Official pass sent to {registration.customer.email}!")
    except Exception as e:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json' or request.method == 'POST':
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
        messages.error(request, f"Failed to send email: {str(e)}")
        
    return redirect('attendee-badge', pass_code=attendee.pass_code)

