import json
from datetime import timedelta
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone

from apps.tenants.models import Tenant
from apps.events.models import Event
from apps.registrations.models import Registration
from apps.payments.models import Order
from apps.verification.models import Verification


def get_current_tenant(request):
    if hasattr(request, '_current_tenant') and request._current_tenant:
        return request._current_tenant
    tenant_id = request.session.get('active_tenant_id')
    tenant = None
    if tenant_id:
        tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
    if not tenant:
        tenant = Tenant.objects.filter(is_active=True).first()
        if tenant:
            request.session['active_tenant_id'] = tenant.id
    request._current_tenant = tenant
    return tenant


@login_required(login_url='login')
def tenant_switch_view(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    request.session['active_tenant_id'] = tenant.id
    request._current_tenant = tenant
    messages.success(request, f"Switched active tenant to {tenant.name}")
    return redirect(request.META.get('HTTP_REFERER', 'dashboard-overview'))


def filter_registrations_queryset(reg_qs, request):
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '').strip()
    reg_code_filter = request.GET.get('reg_code', '').strip()
    customer_filter = request.GET.get('customer', '').strip()
    event_filter = request.GET.get('event_id', '').strip()
    amount_filter = request.GET.get('amount_type', '').strip()
    amount_min = request.GET.get('amount_min', '').strip()
    amount_max = request.GET.get('amount_max', '').strip()
    pass_filter = request.GET.get('pass_filter', '').strip()
    date_preset = request.GET.get('date_preset', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    # Status filter
    if status_filter:
        reg_qs = reg_qs.filter(status=status_filter)

    # Reg Code filter
    if reg_code_filter:
        reg_qs = reg_qs.filter(registration_code__icontains=reg_code_filter)

    # Customer filter (name, email, phone)
    if customer_filter:
        reg_qs = reg_qs.filter(
            Q(customer__name__icontains=customer_filter) |
            Q(customer__email__icontains=customer_filter) |
            Q(customer__phone__icontains=customer_filter)
        )

    # Event filter
    if event_filter:
        reg_qs = reg_qs.filter(event_id=event_filter)

    # Amount filter
    if amount_filter == 'free':
        reg_qs = reg_qs.filter(amount=0)
    elif amount_filter == 'paid':
        reg_qs = reg_qs.filter(amount__gt=0)

    if amount_min:
        try:
            reg_qs = reg_qs.filter(amount__gte=Decimal(amount_min))
        except Exception:
            pass
    if amount_max:
        try:
            reg_qs = reg_qs.filter(amount__lte=Decimal(amount_max))
        except Exception:
            pass

    # Pass Badge filter
    if pass_filter == 'with_pass':
        reg_qs = reg_qs.filter(attendee_pass__isnull=False)
    elif pass_filter == 'without_pass':
        reg_qs = reg_qs.filter(attendee_pass__isnull=True)

    # Date filters
    now = timezone.now()
    if date_preset == 'today':
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        reg_qs = reg_qs.filter(created_at__gte=today_start)
    elif date_preset == '7days':
        reg_qs = reg_qs.filter(created_at__gte=now - timedelta(days=7))
    elif date_preset == '30days':
        reg_qs = reg_qs.filter(created_at__gte=now - timedelta(days=30))
    elif date_from or date_to:
        if date_from:
            try:
                df = timezone.datetime.strptime(date_from, "%Y-%m-%d")
                df_aware = timezone.make_aware(df) if timezone.is_naive(df) else df
                reg_qs = reg_qs.filter(created_at__gte=df_aware)
            except Exception:
                pass
        if date_to:
            try:
                dt = timezone.datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                dt_aware = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                reg_qs = reg_qs.filter(created_at__lte=dt_aware)
            except Exception:
                pass

    # Global text search query
    if search_query:
        reg_qs = reg_qs.filter(
            Q(registration_code__icontains=search_query) |
            Q(customer__name__icontains=search_query) |
            Q(customer__email__icontains=search_query) |
            Q(customer__phone__icontains=search_query) |
            Q(order__order_code__icontains=search_query) |
            Q(event__title__icontains=search_query) |
            Q(attendee_pass__pass_code__icontains=search_query)
        )

    filter_params = {
        'q': search_query,
        'status': status_filter,
        'reg_code': reg_code_filter,
        'customer': customer_filter,
        'event_id': event_filter,
        'amount_type': amount_filter,
        'amount_min': amount_min,
        'amount_max': amount_max,
        'pass_filter': pass_filter,
        'date_preset': date_preset,
        'date_from': date_from,
        'date_to': date_to,
    }

    active_filters_count = sum(1 for k, v in filter_params.items() if v)

    return reg_qs, filter_params, active_filters_count


@login_required(login_url='login')
def overview_dashboard_view(request):
    tenant = get_current_tenant(request)
    if not tenant:
        tenant = Tenant.objects.create(name="Nizhal Community", slug="nizhal-community")
        request.session['active_tenant_id'] = tenant.id
        request._current_tenant = tenant

    from django.core.cache import cache
    cache_key = f"dash_overview_ctx_{tenant.id}"
    cached_ctx = cache.get(cache_key)
    if cached_ctx:
        cached_ctx['tenant'] = tenant
        return render(request, 'dashboard/overview.html', cached_ctx)

    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    # Base QuerySets scoped to tenant
    events_qs = Event.objects.filter(tenant=tenant)
    reg_qs = Registration.objects.filter(event__tenant=tenant)
    order_qs = Order.objects.filter(registration__event__tenant=tenant)

    # 1. Combined Financial & Payment Statistics (1 single SQL aggregation query)
    order_stats = order_qs.aggregate(
        total_revenue=Sum('amount', filter=Q(status='VERIFIED')),
        today_revenue=Sum('amount', filter=Q(status='VERIFIED', created_at__gte=today_start)),
        week_revenue=Sum('amount', filter=Q(status='VERIFIED', created_at__gte=week_start)),
        month_revenue=Sum('amount', filter=Q(status='VERIFIED', created_at__gte=month_start)),
        total_payments_count=Count('id', filter=Q(status='VERIFIED')),
        pending_payments_count=Count('id', filter=Q(status__in=['PENDING', 'UPLOADED', 'VERIFYING'])),
    )

    total_revenue = order_stats['total_revenue'] or Decimal('0.00')
    today_revenue = order_stats['today_revenue'] or Decimal('0.00')
    week_revenue = order_stats['week_revenue'] or Decimal('0.00')
    month_revenue = order_stats['month_revenue'] or Decimal('0.00')
    total_payments_count = order_stats['total_payments_count'] or 0
    pending_payments_count = order_stats['pending_payments_count'] or 0

    # 2. Combined Registration & User Statistics (1 single SQL query)
    reg_stats = reg_qs.aggregate(
        total_registrations=Count('id'),
        verified_reg_count=Count('id', filter=Q(status='COMPLETED')),
    )
    total_registrations = reg_stats['total_registrations'] or 0
    verified_reg_count = reg_stats['verified_reg_count'] or 0
    total_customers = verified_reg_count
    total_passes = verified_reg_count

    # 3. Combined Verification Statistics (1 single SQL query)
    verif_stats = Verification.objects.filter(order__registration__event__tenant=tenant).aggregate(
        review_queue_count=Count('id', filter=Q(decision='MANUAL_REVIEW')),
        auto_verified_count=Count('id', filter=Q(decision='AUTO_VERIFIED')),
    )
    review_queue_count = verif_stats['review_queue_count'] or 0
    auto_verified_count = verif_stats['auto_verified_count'] or 0
    auto_rate = round((auto_verified_count / max(total_payments_count, 1)) * 100, 1)
    pass_conversion_rate = round((verified_reg_count / max(total_registrations, 1)) * 100, 1) if total_registrations > 0 else 0

    # 4. Events with Annotations (1 single query used for list and breakdown)
    all_events = list(events_qs.annotate(
        registrations_count=Count('registrations'),
        paid_count=Count('registrations__order', filter=Q(registrations__order__status='VERIFIED')),
        total_collected=Sum('registrations__order__amount', filter=Q(registrations__order__status='VERIFIED')),
    ).order_by('-created_at'))
    total_events = len(all_events)
    events_breakdown = sorted(all_events, key=lambda e: e.total_collected or Decimal('0.00'), reverse=True)

    context = {
        'tenant': tenant,
        'total_events': total_events,
        'total_registrations': total_registrations,
        'total_customers': total_customers,
        'total_passes': total_passes,
        'verified_reg_count': verified_reg_count,
        'total_revenue': total_revenue,
        'today_revenue': today_revenue,
        'week_revenue': week_revenue,
        'month_revenue': month_revenue,
        'events_breakdown': events_breakdown,
        'total_payments_count': total_payments_count,
        'pending_payments_count': pending_payments_count,
        'review_queue_count': review_queue_count,
        'auto_rate': auto_rate,
        'pass_conversion_rate': pass_conversion_rate,
        'events': all_events,
    }
    cache.set(cache_key, context, timeout=15)
    return render(request, 'dashboard/overview.html', context)

