from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q

from apps.registrations.models import Registration
from apps.notifications.models import EmailLog
from apps.dashboard.views.overview import get_current_tenant


@login_required(login_url='login')
def email_logs_view(request):
    tenant = get_current_tenant(request)
    logs_qs = EmailLog.objects.filter(tenant=tenant).order_by('-sent_at')

    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    event_type_filter = request.GET.get('event_type', '').strip()

    counts = logs_qs.aggregate(
        total_count=Count('id'),
        sent_count=Count('id', filter=Q(status='SENT')),
        simulated_count=Count('id', filter=Q(status='SIMULATED')),
        failed_count=Count('id', filter=Q(status='FAILED')),
    )
    total_count = counts['total_count'] or 0
    sent_count = counts['sent_count'] or 0
    simulated_count = counts['simulated_count'] or 0
    failed_count = counts['failed_count'] or 0

    if status_filter:
        logs_qs = logs_qs.filter(status=status_filter)
    if event_type_filter:
        logs_qs = logs_qs.filter(event_type=event_type_filter)
    if search_query:
        logs_qs = logs_qs.filter(
            Q(subject__icontains=search_query) |
            Q(recipient_name__icontains=search_query) |
            Q(recipient_email__icontains=search_query) |
            Q(body_html__icontains=search_query)
        )

    logs = list(logs_qs[:100])
    selected_id = request.GET.get('id', '')
    selected_email = None
    if selected_id:
        selected_email = next((e for e in logs if str(e.id) == selected_id), None)
    if not selected_email and logs:
        selected_email = logs[0]

    return render(request, 'dashboard/notifications/emails.html', {
        'email_logs': logs,
        'selected_email': selected_email,
        'total_count': total_count,
        'sent_count': sent_count,
        'simulated_count': simulated_count,
        'failed_count': failed_count,
        'search_query': search_query,
        'status_filter': status_filter,
        'event_type_filter': event_type_filter,
        'tenant': tenant
    })


@login_required(login_url='login')
def resend_email_log_view(request, email_id):
    tenant = get_current_tenant(request)
    email_log = get_object_or_404(EmailLog, id=email_id, tenant=tenant)
    from django.core.mail import send_mail
    from django.conf import settings
    
    # If this is a registration pass, re-render fresh HTML with latest centered template
    if email_log.event_type == 'REGISTRATION_COMPLETED':
        reg = Registration.objects.filter(customer__email=email_log.recipient_email, status='COMPLETED', event__tenant=tenant).order_by('-created_at').first()
        if reg:
            try:
                from apps.notifications.services import BANNER_WEB_URL, get_attendee_qr_web_url
                from django.template.loader import render_to_string
                customer = reg.customer
                event = reg.event
                order = getattr(reg, 'order', None)
                pass_code = getattr(reg, 'attendee_pass', None).pass_code if hasattr(reg, 'attendee_pass') and reg.attendee_pass else reg.registration_code
                attendee = getattr(reg, 'attendee_pass', None)
                ticket_count = getattr(reg, 'ticket_count', 1) or 1
                unit_fee = event.registration_fee or 0
                attendee_list = [{'index': 1, 'name': customer.name.title() + ' (Primary)', 'age': '-', 'gender': '-', 'type': 'Primary Ticket Holder', 'email': customer.email, 'phone': customer.phone or '-', 'amount': unit_fee}]
                email_context = {'registration': reg, 'customer': customer, 'event': event, 'order': order, 'attendee': attendee, 'pass_code': pass_code, 'banner_src': BANNER_WEB_URL, 'qr_src': get_attendee_qr_web_url(pass_code), 'attendee_list': attendee_list, 'ticket_count': ticket_count, 'unit_fee': unit_fee}
                fresh_html = render_to_string('emails/registration_confirmed.html', email_context)
                email_log.body_html = fresh_html
                email_log.save(update_fields=['body_html'])
            except Exception:
                pass

    try:
        send_mail(
            subject=email_log.subject,
            message="Please find your official Nizhal Community pass attached.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_log.recipient_email],
            html_message=email_log.body_html,
            fail_silently=False
        )
        email_log.status = 'SENT'
        email_log.error_message = ''
        email_log.save()
        messages.success(request, f"Real email dispatched successfully to {email_log.recipient_email}!")
    except Exception as e:
        email_log.status = 'FAILED'
        email_log.error_message = str(e)
        email_log.save()
        messages.error(request, f"Email delivery failed: {str(e)}")
        
    return redirect(f"/dashboard/emails/?id={email_id}")


@login_required(login_url='login')
def email_preview_view(request, email_id):
    tenant = get_current_tenant(request)
    email_log = get_object_or_404(EmailLog, id=email_id, tenant=tenant)
    html = email_log.body_html or ''
    
    # Ensure clean bounds and responsive preview formatting with pure white canvas
    bounds_css = """
    <style id="nizhal-email-bounds-fix">
        html, body {
            background-color: #ffffff !important;
            margin: 0 !important;
            padding: 0 !important;
            min-height: 100vh !important;
            box-sizing: border-box !important;
        }
        table.ticket-card, table.email-card, .ticket-card, .email-card {
            width: 100% !important;
            max-width: 600px !important;
            margin: 0 auto !important;
            background-color: #ffffff !important;
            box-shadow: none !important;
            border: 1px solid #000000 !important;
            border-radius: 0 !important;
            overflow: hidden !important;
        }
        img {
            max-width: 100% !important;
            height: auto !important;
        }
    </style>
    """
    if '</head>' in html:
        html = html.replace('</head>', bounds_css + '</head>')
    elif '<body>' in html:
        html = html.replace('<body>', '<head>' + bounds_css + '</head><body>')
    else:
        html = '<!DOCTYPE html><html><head>' + bounds_css + '</head><body>' + html + '</body></html>'
        
    return HttpResponse(html, content_type='text/html; charset=utf-8')
