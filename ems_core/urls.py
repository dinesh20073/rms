from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.http import HttpResponse

from apps.registrations import views as reg_views
from apps.payments import views as pay_views
from apps.dashboard import auth_views

urlpatterns = [
    path('favicon.ico', lambda req: redirect('/static/images/nizhal_logo.png')),
    path('admin/', admin.site.urls),
    
    # Secure Authentication
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    
    # Root endpoint (renders login view or redirects to dashboard if authenticated)
    path('', auth_views.login_view, name='root-home'),
    # Custom AI Innovators registration page (bright theme)
    path('register/ai-innovators-2026/', reg_views.ai_innovators_register_view, name='ai-innovators-register'),

    # Public Registration & Checkout Journey (supports both with & without trailing slash)
    path('register/<slug:slug>/', reg_views.public_registration_view, name='public-register'),
    path('register/<slug:slug>', reg_views.public_registration_view),
    path('register/<slug:slug>/submit/', reg_views.submit_registration_view, name='public-register-submit'),
    path('register/<slug:slug>/submit', reg_views.submit_registration_view),
    path('pay/<str:order_code>/', pay_views.payment_checkout_view, name='payment-checkout'),
    path('pay/<str:order_code>', pay_views.payment_checkout_view),
    path('pay/<str:order_code>/proof/', pay_views.upload_proof_view, name='payment-proof-upload'),
    path('pay/<str:order_code>/proof', pay_views.upload_proof_view),
    path('pay/<str:order_code>/simulate-proof/', pay_views.simulate_test_proof_view, name='payment-simulate-proof'),
    path('pay/<str:order_code>/simulate-proof', pay_views.simulate_test_proof_view),
    path('status/<str:registration_code>/', reg_views.registration_status_view, name='registration-status'),
    path('status/<str:registration_code>', reg_views.registration_status_view),
    path('pass/<str:pass_code>/', reg_views.attendee_badge_view, name='attendee-badge'),
    path('pass/<str:pass_code>', reg_views.attendee_badge_view),
    path('pass/<str:pass_code>/send-email/', reg_views.send_pass_email_view, name='send-pass-email'),
    path('pass/<str:pass_code>/send-email', reg_views.send_pass_email_view),

    # Admin Operations Dashboard
    path('dashboard/', include('apps.dashboard.urls')),

    # Partner REST API (v1)
    path('api/v1/', include('apps.api_v1.urls')),
]

from django.urls import re_path
from django.views.static import serve
from django.http import JsonResponse
from django.shortcuts import render

urlpatterns += [
    re_path(r'^(?:register/)?static/(?P<path>.*)$', serve, {'document_root': settings.STATICFILES_DIRS[0]}),
    re_path(r'^(?:register/)?media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

def custom_404_view(request, exception=None):
    """
    Handles 404s safely:
    - Returns JSON for API endpoints
    - Any wrong page of admin redirects to the admin root URL (e.g. https://www.admin.nizhalcommunity.in/)
    - Customer-facing public site (nizhalcommunity.in) renders registration_closed.html
    """
    if request.path.startswith('/api/'):
        return JsonResponse({'error': 'Endpoint not found', 'status': 404}, status=404)

    host = request.get_host().lower()
    is_admin_host = (
        'admin.nizhalcommunity.in' in host
        or 'admin-nizhal-community' in host
        or host.startswith('admin.')
    )

    if is_admin_host:
        return redirect(f"{request.scheme}://{host}/")

    return render(request, 'public/registration_closed.html', {
        'closed_reason': 'The page you requested could not be found.',
    }, status=404)

handler404 = 'ems_core.urls.custom_404_view'
