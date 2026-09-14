import csv
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from apps.events.models import Event
from apps.registrations.models import Registration
from django.db.models import Prefetch
from apps.verification.models import PaymentEvidence
from apps.dashboard.views.overview import get_current_tenant, filter_registrations_queryset


@login_required(login_url='login')
def registrations_list_view(request):
    tenant = get_current_tenant(request)
    qs = Registration.objects.filter(event__tenant=tenant).select_related(
        'customer', 'event', 'order', 'attendee_pass',
        'order__verification', 'order__verification__evidence'
    ).prefetch_related(
        Prefetch('order__evidence_records', queryset=PaymentEvidence.objects.defer('image_base64'))
    ).defer(
        'order__qr_code_base64',
        'order__verification__evidence__image_base64'
    ).order_by('-created_at')
    qs, filter_params, active_filters_count = filter_registrations_queryset(qs, request)
    events = Event.objects.filter(tenant=tenant)
    return render(request, 'dashboard/registrations/list.html', {
        'registrations': qs,
        'events': events,
        'filter_params': filter_params,
        'active_filters_count': active_filters_count,
        'search_query': filter_params.get('q', ''),
        'status_filter': filter_params.get('status', ''),
        'event_filter': filter_params.get('event_id', ''),
        'tenant': tenant
    })


@login_required(login_url='login')
def export_attendees_csv(request, event_id):
    tenant = get_current_tenant(request)
    event = get_object_or_404(Event, id=event_id, tenant=tenant)
    include_all = request.GET.get('all') == '1'
    registrations = event.registrations.select_related('customer', 'order', 'attendee_pass').all()
    if not include_all:
        from django.db.models import Q
        registrations = registrations.filter(
            Q(order__status='VERIFIED') |
            Q(status='COMPLETED') |
            Q(attendee_pass__isnull=False) |
            (Q(amount=0) & ~Q(status__in=['FAILED', 'CANCELLED']))
        )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendees_{event.slug}_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Registration Code', 'Attendee Name', 'Email', 'Phone', 'Company', 'Designation', 'Pass Code', 'Payment Status', 'Registration Status', 'Amount', 'Date'])

    for r in registrations:
        pass_code = r.attendee_pass.pass_code if hasattr(r, 'attendee_pass') else ''
        order_status = r.order.status if hasattr(r, 'order') else 'N/A'
        writer.writerow([
            r.registration_code,
            r.customer.name,
            r.customer.email,
            r.customer.phone,
            r.customer.company,
            r.customer.designation,
            pass_code,
            order_status,
            r.status,
            r.amount,
            r.created_at.strftime('%Y-%m-%d %H:%M')
        ])

    return response


@login_required(login_url='login')
def send_registration_email_view(request, registration_code):
    tenant = get_current_tenant(request)
    registration = get_object_or_404(Registration, registration_code=registration_code, event__tenant=tenant)
    from apps.notifications.services import send_registration_success_email, send_payment_reminder_email
    
    email_type = request.GET.get('type', 'auto')
    
    if registration.status == 'COMPLETED':
        send_registration_success_email(registration)
        messages.success(request, f"Official Confirmation & Attendee Pass email dispatched to {registration.customer.email}!")
    elif registration.status in ['PENDING', 'FAILED'] or email_type == 'reminder':
        send_payment_reminder_email(registration)
        messages.success(request, f"Payment reminder & UPI retry instructions dispatched to {registration.customer.email}!")
    elif registration.status == 'MANUAL_REVIEW':
        messages.warning(request, "Registration is currently under manual review. Official pass email will be dispatched automatically once approved in the verification queue.")
    else:
        messages.info(request, "No email action available for this registration status.")
        
    return redirect(request.META.get('HTTP_REFERER', 'dashboard-overview'))


@login_required(login_url='login')
def change_registration_status_view(request, registration_code):
    tenant = get_current_tenant(request)
    registration = get_object_or_404(Registration, registration_code=registration_code, event__tenant=tenant)
    user = request.user if request.user.is_authenticated else None

    target_status = request.POST.get('target_status') or request.GET.get('target_status') or ''
    target_status = target_status.strip().upper()

    is_currently_accepted = (
        registration.status == 'COMPLETED' or 
        (hasattr(registration, 'order') and registration.order and registration.order.status == 'VERIFIED')
    )

    if not target_status:
        target_status = 'FAIL' if is_currently_accepted else 'ACCEPT'

    from apps.verification.engine import VerificationEngine
    from apps.registrations.models import Attendee
    from apps.audit.services import log_audit_event

    if target_status == 'ACCEPT':
        if hasattr(registration, 'order') and registration.order:
            VerificationEngine.manual_approve(
                registration.order,
                reviewer_user=user,
                notes=f"Status changed to Accepted by {user.username if user else 'Admin'}"
            )
        else:
            registration.status = 'COMPLETED'
            registration.save()
            Attendee.objects.get_or_create(registration=registration)
            log_audit_event('REGISTRATION_ACCEPTED', registration.registration_code, {}, tenant=tenant, actor=user.username if user else 'Admin')
        messages.success(request, f"Registration {registration.registration_code} ({registration.customer.name}) marked as Accepted (Payment Verified)!")
    elif target_status == 'FAIL':
        if hasattr(registration, 'order') and registration.order:
            VerificationEngine.manual_reject(
                registration.order,
                reviewer_user=user,
                notes=f"Status changed to Failed by {user.username if user else 'Admin'}"
            )
        else:
            registration.status = 'FAILED'
            registration.save()
            log_audit_event('REGISTRATION_FAILED', registration.registration_code, {}, tenant=tenant, actor=user.username if user else 'Admin')
        messages.warning(request, f"Registration {registration.registration_code} ({registration.customer.name}) marked as Failed.")

    return redirect(request.META.get('HTTP_REFERER', 'dashboard-registrations-list'))


@login_required(login_url='login')
def registration_bulk_action_view(request):
    if request.method != 'POST':
        return redirect(request.META.get('HTTP_REFERER', 'dashboard-registrations-list'))

    tenant = get_current_tenant(request)
    action = request.POST.get('action')
    notes = request.POST.get('notes', '').strip()
    codes_raw = request.POST.getlist('selected_codes')
    if not codes_raw:
        val = request.POST.get('selected_codes', '')
        codes_raw = [val] if val else []

    reg_codes = []
    for c in codes_raw:
        if isinstance(c, str):
            for part in c.split(','):
                part = part.strip()
                if part:
                    reg_codes.append(part)

    if not reg_codes:
        messages.warning(request, "No registrations selected.")
        return redirect(request.META.get('HTTP_REFERER', 'dashboard-registrations-list'))

    from django.db.models import Q
    query = Registration.objects.filter(
        Q(registration_code__in=reg_codes) | Q(id__in=[int(c) for c in reg_codes if c.isdigit()])
    )
    if tenant:
        query = query.filter(event__tenant=tenant)
    registrations = list(query.select_related('order', 'customer', 'event'))

    user = request.user if request.user.is_authenticated else None
    count = len(registrations)

    if count == 0:
        messages.warning(request, "Selected registrations were not found.")
        return redirect(request.META.get('HTTP_REFERER', 'dashboard-registrations-list'))

    from apps.verification.engine import VerificationEngine
    from apps.registrations.models import Attendee
    from apps.audit.services import log_audit_event
    from apps.verification.models import PaymentEvidence

    if action == 'APPROVE':
        for reg in registrations:
            if hasattr(reg, 'order') and reg.order:
                VerificationEngine.manual_approve(reg.order, reviewer_user=user, notes=notes or 'Bulk approved by admin')
            else:
                reg.status = 'COMPLETED'
                reg.save()
                Attendee.objects.get_or_create(registration=reg)
                log_audit_event('REGISTRATION_ACCEPTED', reg.registration_code, {}, tenant=tenant, actor=user.username if user else 'Admin')
        messages.success(request, f"Successfully marked {count} registration(s) as Payment Received (Verified).")

    elif action == 'REJECT':
        for reg in registrations:
            if hasattr(reg, 'order') and reg.order:
                VerificationEngine.manual_reject(reg.order, reviewer_user=user, notes=notes or 'Bulk rejected by admin')
            else:
                reg.status = 'FAILED'
                reg.save()
                Attendee.objects.filter(registration=reg).delete()
                log_audit_event('REGISTRATION_FAILED', reg.registration_code, {}, tenant=tenant, actor=user.username if user else 'Admin')
        messages.warning(request, f"Successfully marked {count} registration(s) as Not Received (Failed).")

    elif action == 'DELETE_IMAGE':
        deleted_count = 0
        for reg in registrations:
            if hasattr(reg, 'order') and reg.order:
                for ev in PaymentEvidence.objects.filter(order=reg.order):
                    if ev.screenshot:
                        try:
                            ev.screenshot.delete(save=False)
                        except Exception:
                            pass
                        ev.screenshot = None
                    ev.image_base64 = ''
                    ev.save()
                    deleted_count += 1
                if hasattr(reg.order, 'proof_image') and reg.order.proof_image:
                    try:
                        reg.order.proof_image.delete(save=False)
                    except Exception:
                        pass
                    reg.order.proof_image = None
                    reg.order.save()
                log_audit_event('PAYMENT_IMAGE_DELETED', reg.order.order_code, {'reg_code': reg.registration_code}, tenant=tenant, actor=user.username if user else 'Admin')
        messages.success(request, f"Successfully purged payment proof images for {deleted_count} record(s).")

    elif action == 'DELETE':
        for reg in registrations:
            log_audit_event(
                action='REGISTRATION_DELETED',
                reference_id=reg.registration_code,
                details={'event': reg.event.title, 'customer': reg.customer.name},
                tenant=tenant,
                actor=user.username if user else 'Admin'
            )
            reg.delete()
        messages.success(request, f"Successfully deleted {count} registration record(s).")

    else:
        messages.error(request, "Invalid bulk action requested.")

    return redirect(request.META.get('HTTP_REFERER', 'dashboard-registrations-list'))

