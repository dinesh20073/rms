import time
from apps.tenants.models import Tenant
from apps.verification.models import Verification

_REVIEW_COUNT_CACHE = {}  # {tenant_id: (count, timestamp)}
_TENANTS_CACHE = ([], 0)  # (all_tenants, timestamp)

def global_context(request):
    """
    Ultra-fast cached context processor: supplies active tenant and pending review count.
    Avoids redundant database queries across requests and live-sync polling.
    """
    if not request.path.startswith('/dashboard/') or not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'all_tenants': [],
            'current_tenant': None,
            'pending_reviews_count': 0,
        }

    try:
        now = time.monotonic()
        global _TENANTS_CACHE, _REVIEW_COUNT_CACHE

        # 1. Tenant lookup with 30s cache
        tenants_list, tenants_time = _TENANTS_CACHE
        if now - tenants_time > 30 or not tenants_list:
            tenants_list = list(Tenant.objects.filter(is_active=True))
            _TENANTS_CACHE = (tenants_list, now)
        all_tenants = tenants_list

        current_tenant = getattr(request, '_current_tenant', None)
        if not current_tenant:
            tenant_id = request.session.get('active_tenant_id')
            if tenant_id:
                for t in all_tenants:
                    if t.id == tenant_id:
                        current_tenant = t
                        break
            if not current_tenant and all_tenants:
                current_tenant = all_tenants[0]
            request._current_tenant = current_tenant

        # 2. Pending review count with 15s cache
        pending_reviews_count = 0
        if current_tenant:
            t_id = current_tenant.id
            cached_count, count_time = _REVIEW_COUNT_CACHE.get(t_id, (None, 0))
            if cached_count is not None and (now - count_time < 15):
                pending_reviews_count = cached_count
            else:
                pending_reviews_count = Verification.objects.filter(
                    order__registration__event__tenant=current_tenant,
                    decision='MANUAL_REVIEW'
                ).count()
                _REVIEW_COUNT_CACHE[t_id] = (pending_reviews_count, now)

        return {
            'all_tenants': all_tenants,
            'current_tenant': current_tenant,
            'pending_reviews_count': pending_reviews_count,
        }
    except Exception:
        return {
            'all_tenants': [],
            'current_tenant': None,
            'pending_reviews_count': 0,
        }

