from apps.tenants.models import Tenant
from apps.verification.models import Verification

def global_context(request):
    """
    Supplies active tenant, pending review count, and quick stats for the UI navigation.
    """
    tenants = Tenant.objects.filter(is_active=True)
    tenant_id = request.session.get('active_tenant_id')
    current_tenant = None

    if tenant_id:
        current_tenant = tenants.filter(id=tenant_id).first()
    if not current_tenant and tenants.exists():
        current_tenant = tenants.first()
        request.session['active_tenant_id'] = current_tenant.id

    pending_reviews_count = 0
    if current_tenant:
        pending_reviews_count = Verification.objects.filter(
            order__registration__event__tenant=current_tenant,
            decision='MANUAL_REVIEW'
        ).count()

    return {
        'all_tenants': tenants,
        'current_tenant': current_tenant,
        'pending_reviews_count': pending_reviews_count,
    }
