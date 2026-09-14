from datetime import timedelta
from decimal import Decimal
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.utils import timezone

from apps.events.models import Event
from apps.payments.models import Order
from apps.dashboard.views.overview import get_current_tenant


@login_required(login_url='login')
def revenue_analytics_view(request):
    tenant = get_current_tenant(request)
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=now.weekday())
    month_start = today_start.replace(day=1)

    verified_orders = Order.objects.filter(registration__event__tenant=tenant, status='VERIFIED')

    rev_stats = verified_orders.aggregate(
        total_rev=Sum('amount'),
        today_rev=Sum('amount', filter=Q(created_at__gte=today_start)),
        week_rev=Sum('amount', filter=Q(created_at__gte=week_start)),
        month_rev=Sum('amount', filter=Q(created_at__gte=month_start)),
    )
    today_rev = rev_stats['today_rev'] or Decimal('0.00')
    week_rev = rev_stats['week_rev'] or Decimal('0.00')
    month_rev = rev_stats['month_rev'] or Decimal('0.00')
    total_rev = rev_stats['total_rev'] or Decimal('0.00')

    # Breakdown by Event
    events_breakdown = Event.objects.filter(tenant=tenant).annotate(
        paid_count=Count('registrations__order', filter=Q(registrations__order__status='VERIFIED')),
        total_collected=Sum('registrations__order__amount', filter=Q(registrations__order__status='VERIFIED'))
    ).order_by('-total_collected')

    return render(request, 'dashboard/revenue/analytics.html', {
        'today_rev': today_rev,
        'week_rev': week_rev,
        'month_rev': month_rev,
        'total_rev': total_rev,
        'events_breakdown': events_breakdown,
        'tenant': tenant
    })
