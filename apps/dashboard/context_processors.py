from apps.tenants.models import Tenant
from apps.verification.models import Verification

def global_context(request):
    """
    Ultra-fast context processor: supplies active tenant and pending review count.
    Avoids database queries for unauthenticated or public/static paths.
    """
    if not request.path.startswith('/dashboard/') or not getattr(request, 'user', None) or not request.user.is_authenticated:
        return {
            'all_tenants': [],
            'current_tenant': None,
            'pending_reviews_count': 0,
        }

    try:
        if hasattr(request, '_current_tenant') and request._current_tenant:
            current_tenant = request._current_tenant
            all_tenants = getattr(request, '_all_tenants', None) or list(Tenant.objects.filter(is_active=True))
        else:
            all_tenants = list(Tenant.objects.filter(is_active=True))
            request._all_tenants = all_tenants
            tenant_id = request.session.get('active_tenant_id')
            current_tenant = None
            if tenant_id:
                for t in all_tenants:
                    if t.id == tenant_id:
                        current_tenant = t
                        break
            if not current_tenant and all_tenants:
                current_tenant = all_tenants[0]
            request._current_tenant = current_tenant

        pending_reviews_count = 0
        if current_tenant:
            pending_reviews_count = Verification.objects.filter(
                order__registration__event__tenant=current_tenant,
                decision='MANUAL_REVIEW'
            ).count()

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

