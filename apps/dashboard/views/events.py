import base64
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone

from apps.events.models import Event
from apps.forms_builder.models import Form
from apps.audit.services import log_audit_event
from apps.dashboard.views.overview import get_current_tenant


@login_required(login_url='login')
def events_list_view(request):
    tenant = get_current_tenant(request)
    events = Event.objects.filter(tenant=tenant).annotate(
        registrations_count=Count('registrations'),
        revenue_sum=Sum('registrations__order__amount', filter=Q(registrations__order__status='VERIFIED'))
    ).order_by('-created_at')

    forms_data = []
    for ev in events:
        form_obj, created = Form.objects.get_or_create(event=ev)
        if created or not form_obj.fields.exists():
            form_obj.create_default_fields()
        forms_data.append({
            'event': ev,
            'form': form_obj,
            'fields_count': form_obj.fields.count(),
            'responses_count': ev.registrations_count or 0,
            'revenue_sum': ev.revenue_sum or Decimal('0.00'),
        })

    return render(request, 'dashboard/events/list.html', {
        'forms_data': forms_data,
        'events': events,
        'tenant': tenant
    })


@login_required(login_url='login')
def create_event_view(request):
    tenant = get_current_tenant(request)
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        fee_raw = request.POST.get('registration_fee', '0')
        upi_id = request.POST.get('upi_id', 'dinesh.b@superyes').strip()
        upi_name = request.POST.get('upi_name', 'Dinesh').strip()
        venue = request.POST.get('venue', 'Online / Virtual').strip()
        status_val = request.POST.get('status', 'OPEN')

        try:
            fee = Decimal(fee_raw)
        except Exception:
            fee = Decimal('0.00')

        event = Event(
            tenant=tenant,
            title=title,
            description=description,
            registration_fee=fee,
            upi_id=upi_id,
            upi_name=upi_name,
            venue=venue,
            status=status_val
        )

        start_date_raw = request.POST.get('event_start_date', '').strip()
        reg_opens_raw = request.POST.get('registration_opens', '').strip()
        reg_closes_raw = request.POST.get('registration_closes', '').strip()
        max_cap_raw = request.POST.get('max_capacity', '').strip()

        if start_date_raw:
            try:
                event.event_start_date = timezone.datetime.fromisoformat(start_date_raw)
                if timezone.is_naive(event.event_start_date):
                    event.event_start_date = timezone.make_aware(event.event_start_date)
            except Exception:
                pass

        if reg_opens_raw:
            try:
                event.registration_opens = timezone.datetime.fromisoformat(reg_opens_raw)
                if timezone.is_naive(event.registration_opens):
                    event.registration_opens = timezone.make_aware(event.registration_opens)
            except Exception:
                pass

        if reg_closes_raw:
            try:
                event.registration_closes = timezone.datetime.fromisoformat(reg_closes_raw)
                if timezone.is_naive(event.registration_closes):
                    event.registration_closes = timezone.make_aware(event.registration_closes)
            except Exception:
                pass

        unlimited_cap = request.POST.get('unlimited_capacity') in ('1', 'true', 'on', True)
        if unlimited_cap or max_cap_raw == '0' or not max_cap_raw:
            event.max_capacity = None
        elif max_cap_raw and str(max_cap_raw).isdigit():
            event.max_capacity = int(max_cap_raw)

        if request.FILES.get('upi_qr_code'):
            qr_file = request.FILES['upi_qr_code']
            content = qr_file.read()
            qr_file.seek(0)
            b64 = base64.b64encode(content).decode('utf-8')
            name = str(getattr(qr_file, 'name', '')).lower()
            mime = 'image/png' if name.endswith('.png') else ('image/webp' if name.endswith('.webp') else 'image/jpeg')
            event.upi_qr_base64 = f"data:{mime};base64,{b64}"
            event.upi_qr_code = qr_file
        event.save()

        # Initialize form builder
        form_obj = Form.objects.create(event=event, title=f"Registration - {event.title}")
        form_obj.create_default_fields()

        messages.success(request, f"Event '{event.title}' created successfully with code {event.event_code}!")
        return redirect('dashboard-event-detail', event_id=event.id)

    return render(request, 'dashboard/events/create.html', {'tenant': tenant})


@login_required(login_url='login')
def event_detail_view(request, event_id):
    tenant = get_current_tenant(request)
    event = get_object_or_404(Event, id=event_id, tenant=tenant)
    all_registrations = event.registrations.select_related('customer', 'order', 'attendee_pass').order_by('-created_at')

    # Core Metrics
    total_reg = all_registrations.count()
    completed_reg = all_registrations.filter(status='COMPLETED').count()
    paid_orders = all_registrations.filter(order__status='VERIFIED').count()
    pending_reg = all_registrations.filter(status='PENDING').count()
    review_reg = all_registrations.filter(status='MANUAL_REVIEW').count()
    revenue = all_registrations.filter(order__status='VERIFIED').aggregate(total=Sum('order__amount'))['total'] or Decimal('0.00')

    # Attendees: Only registrations where payment has cleared (or verified pass issued / completed)
    cleared_filter = (
        Q(order__status='VERIFIED') |
        Q(status='COMPLETED') |
        Q(attendee_pass__isnull=False) |
        (Q(amount=0) & ~Q(status__in=['FAILED', 'CANCELLED']))
    )
    cleared_attendees = all_registrations.filter(cleared_filter)
    pending_unverified_count = total_reg - cleared_attendees.count()

    # Demographics & Ticket Count Calculations (based on cleared attendees)
    total_tickets = 0
    male_count = 0
    female_count = 0
    other_gender_count = 0
    age_distribution = {
        'Under 18': 0,
        '18 - 24': 0,
        '25 - 34': 0,
        '35 - 44': 0,
        '45+': 0
    }

    demographics_target = cleared_attendees if cleared_attendees.exists() else all_registrations
    for reg in demographics_target:
        responses = reg.form_responses or {}
        # Ticket count
        try:
            t_count = int(responses.get('ticket_count', 1))
        except (ValueError, TypeError):
            t_count = 1
        total_tickets += t_count

        # Gender count from actual form responses
        gender = str(responses.get('gender', '')).lower()
        if 'female' in gender or 'woman' in gender:
            female_count += 1
        elif 'male' in gender or 'man' in gender:
            male_count += 1
        elif gender:
            other_gender_count += 1

        # Age category from actual form responses
        age_cat = str(responses.get('age_category', '')).lower()
        if '18' in age_cat and '24' in age_cat:
            age_distribution['18 - 24'] += 1
        elif '25' in age_cat and '34' in age_cat:
            age_distribution['25 - 34'] += 1
        elif '35' in age_cat and '44' in age_cat:
            age_distribution['35 - 44'] += 1
        elif '45' in age_cat or '55' in age_cat:
            age_distribution['45+'] += 1
        elif 'under' in age_cat:
            age_distribution['Under 18'] += 1

    cleared_count = cleared_attendees.count()
    context = {
        'event': event,
        'registrations': cleared_attendees,  # Only cleared payment attendees in the attendees table!
        'cleared_attendees': cleared_attendees,
        'cleared_count': cleared_count,
        'pending_unverified_count': pending_unverified_count,
        'all_registrations': all_registrations,
        'total_reg': total_reg,
        'completed_reg': completed_reg,
        'paid_orders': paid_orders,
        'pending_reg': pending_reg,
        'review_reg': review_reg,
        'revenue': revenue,
        'total_tickets': max(total_tickets, cleared_count),
        'male_count': male_count,
        'female_count': female_count,
        'other_gender_count': other_gender_count,
        'age_distribution': age_distribution,
    }
    return render(request, 'dashboard/events/detail.html', context)


@login_required(login_url='login')
def edit_event_view(request, event_id):
    tenant = get_current_tenant(request)
    event = get_object_or_404(Event, id=event_id, tenant=tenant)
    form_obj, _ = Form.objects.get_or_create(event=event)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        fee_raw = request.POST.get('registration_fee', '0')
        upi_id = request.POST.get('upi_id', '').strip()
        upi_name = request.POST.get('upi_name', '').strip()
        venue = request.POST.get('venue', '').strip()
        status_val = request.POST.get('status', 'OPEN')
        max_capacity_raw = request.POST.get('max_capacity', '').strip()
        start_date_raw = request.POST.get('event_start_date', '').strip()
        reg_opens_raw = request.POST.get('registration_opens', '').strip()
        reg_closes_raw = request.POST.get('registration_closes', '').strip()

        try:
            event.registration_fee = Decimal(fee_raw)
        except Exception:
            pass

        if title:
            event.title = title
        event.description = description
        if upi_id:
            event.upi_id = upi_id
        if upi_name:
            event.upi_name = upi_name
        event.venue = venue
        event.status = 'OPEN' if status_val == 'OPEN' else 'CLOSED'

        unlimited_cap = request.POST.get('unlimited_capacity') in ('1', 'true', 'on', True)
        if unlimited_cap or max_capacity_raw == '0' or not max_capacity_raw:
            event.max_capacity = None
        elif max_capacity_raw and str(max_capacity_raw).isdigit():
            event.max_capacity = int(max_capacity_raw)

        if start_date_raw:
            try:
                event.event_start_date = timezone.datetime.fromisoformat(start_date_raw)
                if timezone.is_naive(event.event_start_date):
                    event.event_start_date = timezone.make_aware(event.event_start_date)
            except Exception:
                pass
        else:
            event.event_start_date = None

        if reg_opens_raw:
            try:
                event.registration_opens = timezone.datetime.fromisoformat(reg_opens_raw)
                if timezone.is_naive(event.registration_opens):
                    event.registration_opens = timezone.make_aware(event.registration_opens)
            except Exception:
                pass
        else:
            event.registration_opens = None

        if reg_closes_raw:
            try:
                event.registration_closes = timezone.datetime.fromisoformat(reg_closes_raw)
                if timezone.is_naive(event.registration_closes):
                    event.registration_closes = timezone.make_aware(event.registration_closes)
            except Exception:
                pass
        else:
            event.registration_closes = None

        if request.FILES.get('upi_qr_code'):
            qr_file = request.FILES['upi_qr_code']
            content = qr_file.read()
            qr_file.seek(0)
            b64 = base64.b64encode(content).decode('utf-8')
            name = str(getattr(qr_file, 'name', '')).lower()
            mime = 'image/png' if name.endswith('.png') else ('image/webp' if name.endswith('.webp') else 'image/jpeg')
            event.upi_qr_base64 = f"data:{mime};base64,{b64}"
            event.upi_qr_code = qr_file

        event.save()

        form_desc = request.POST.get('form_description', '').strip()
        if form_desc is not None:
            form_obj.description = form_desc
            form_obj.save()

        log_audit_event('EVENT_UPDATED', event.event_code, {'title': event.title}, tenant=tenant, actor=request.user.username if request.user else 'Admin')
        messages.success(request, f"Event '{event.title}' updated successfully!")
        return redirect('dashboard-event-detail', event_id=event.id)

    return render(request, 'dashboard/events/edit.html', {
        'event': event,
        'form_obj': form_obj,
        'tenant': tenant
    })


@login_required(login_url='login')
def delete_event_view(request, event_id):
    tenant = get_current_tenant(request)
    event = get_object_or_404(Event, id=event_id, tenant=tenant)

    if request.method == 'POST':
        title = event.title
        event_code = event.event_code
        log_audit_event(
            action='EVENT_DELETED',
            reference_id=event_code,
            details={'title': title, 'event_id': event_id},
            tenant=tenant,
            actor=request.user.username if request.user else 'Admin'
        )
        event.delete()
        messages.success(request, f"Event '{title}' ({event_code}) and its associated forms and records were deleted successfully.")
        return redirect('dashboard-events-list')

    return redirect('dashboard-event-detail', event_id=event.id)
