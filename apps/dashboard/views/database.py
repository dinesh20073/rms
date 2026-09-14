import csv
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum
from django.db.models.functions import Lower
from django.utils import timezone

from apps.registrations.models import Customer, Registration
from apps.dashboard.views.overview import get_current_tenant

@login_required(login_url='login')
def database_view(request):
    tenant = get_current_tenant(request)
    # Automatically merge duplicate profiles sharing same mobile number or email ID
    from apps.registrations.services import consolidate_tenant_customers
    consolidate_tenant_customers(tenant)

    search_query = request.GET.get('q', '').strip()

    customers_qs = Customer.objects.filter(
        tenant=tenant,
        registrations__isnull=False
    ).distinct().prefetch_related(
        'registrations',
        'registrations__event',
        'registrations__order',
        'registrations__attendee_pass'
    ).order_by(Lower('name').asc())

    if search_query:
        customers_qs = customers_qs.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(company__icontains=search_query) |
            Q(designation__icontains=search_query) |
            Q(reg_id__icontains=search_query)
        )

    # Core Metrics from real database
    total_contacts = customers_qs.count()
    total_registrations = Registration.objects.filter(event__tenant=tenant).count()
    verified_attendees = Registration.objects.filter(event__tenant=tenant, status='COMPLETED').count()

    # Calculate Gender Breakdown for all bookings
    all_regs = Registration.objects.filter(event__tenant=tenant)
    male_bookings = 0
    female_bookings = 0
    other_bookings = 0
    for r in all_regs:
        g = (r.form_responses.get('Gender') or r.form_responses.get('gender') or '').strip().lower()
        if 'female' in g:
            female_bookings += 1
        elif 'male' in g:
            male_bookings += 1
        elif g:
            other_bookings += 1

    # Enhance customer objects with helper attributes for template
    customer_list = []
    male_count = 0
    female_count = 0
    other_count = 0

    for c in customers_qs:
        regs = list(c.registrations.all())
        completed_regs = [r for r in regs if r.status == 'COMPLETED']
        pending_regs = [r for r in regs if r.status in ['PENDING', 'MANUAL_REVIEW']]
        total_paid = sum(r.amount for r in completed_regs)

        # Detect candidate gender from registration responses
        gender_raw = ''
        for r in regs:
            g = (r.form_responses.get('Gender') or r.form_responses.get('gender') or '').strip()
            if g:
                gender_raw = g
                break

        g_lower = gender_raw.lower()
        if 'female' in g_lower:
            gender_clean = 'Female'
            female_count += 1
        elif 'male' in g_lower:
            gender_clean = 'Male'
            male_count += 1
        elif g_lower:
            gender_clean = 'Other'
            other_count += 1
        else:
            gender_clean = 'Other'
            other_count += 1

        # Collect distinct registered events for this attendee
        events_dict = {}
        for r in regs:
            if r.event:
                if r.event.id not in events_dict:
                    events_dict[r.event.id] = {
                        'id': r.event.id,
                        'title': r.event.title,
                        'count': 1
                    }
                else:
                    events_dict[r.event.id]['count'] += 1
        registered_events = list(events_dict.values())

        customer_list.append({
            'id': c.id,
            'name': c.name,
            'email': c.email,
            'phone': c.phone or '-',
            'company': c.company,
            'designation': c.designation,
            'gender': gender_clean,
            'reg_id': c.reg_id or f"REG-{c.id:04d}",
            'created_at': c.created_at,
            'registrations': regs,
            'events': registered_events,
            'reg_count': len(regs),
            'completed_count': len(completed_regs),
            'pending_count': len(pending_regs),
            'total_paid': total_paid,
            'latest_registration': regs[0] if regs else None,
        })

    # Always sort strictly A to Z by attendee name
    customer_list.sort(key=lambda x: (x.get('name') or '').strip().lower())

    return render(request, 'dashboard/customers/database.html', {
        'customers': customer_list,
        'search_query': search_query,
        'total_contacts': len(customer_list),
        'total_registrations': total_registrations,
        'verified_attendees': verified_attendees,
        'male_count': male_count,
        'female_count': female_count,
        'other_count': other_count,
        'male_bookings': male_bookings,
        'female_bookings': female_bookings,
        'other_bookings': other_bookings,
        'tenant': tenant,
    })

@login_required(login_url='login')
def export_customers_csv(request):
    tenant = get_current_tenant(request)
    from apps.registrations.services import consolidate_tenant_customers
    consolidate_tenant_customers(tenant)

    customers = Customer.objects.filter(
        tenant=tenant,
        registrations__isnull=False
    ).distinct().prefetch_related('registrations', 'registrations__event').order_by(Lower('name').asc())

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="database_contacts_{timezone.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Reg ID', 'Name', 'Email ID', 'Phone Number', 'Company / Org', 'Designation', 'Total Registrations', 'Latest Event', 'Date Joined'])

    for c in customers:
        regs = list(c.registrations.all())
        latest_event = regs[0].event.title if regs and regs[0].event else '-'
        writer.writerow([
            c.reg_id or f"REG-{c.id:04d}",
            c.name,
            c.email,
            c.phone or '-',
            c.company or '-',
            c.designation or '-',
            len(regs),
            latest_event,
            c.created_at.strftime('%Y-%m-%d %H:%M')
        ])

    return response
