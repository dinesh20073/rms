from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from apps.tenants.models import ApiKey
from apps.dashboard.views.overview import get_current_tenant


@login_required(login_url='login')
def partner_api_view(request):
    tenant = get_current_tenant(request)
    if request.method == 'POST' and 'generate_key' in request.POST:
        name = request.POST.get('key_name', 'Partner API Key').strip()
        ApiKey.objects.create(tenant=tenant, name=name)
        messages.success(request, "New API Key generated.")
        return redirect('dashboard-partner-api')

    api_keys = tenant.api_keys.all()
    sample_event = tenant.events.first()

    return render(request, 'dashboard/partner/api.html', {
        'tenant': tenant,
        'api_keys': api_keys,
        'sample_event': sample_event
    })
