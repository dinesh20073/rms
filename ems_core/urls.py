from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

from apps.registrations import views as reg_views
from apps.payments import views as pay_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Root redirects to Dashboard
    path('', lambda req: redirect('dashboard-overview'), name='root-home'),
    # Custom AI Innovators registration page (bright theme)
    path('register/ai-innovators-2026/', reg_views.ai_innovators_register_view, name='ai-innovators-register'),

    # Public Registration & Checkout Journey
    path('register/<slug:slug>/', reg_views.public_registration_view, name='public-register'),
    path('register/<slug:slug>/submit/', reg_views.submit_registration_view, name='public-register-submit'),
    path('pay/<str:order_code>/', pay_views.payment_checkout_view, name='payment-checkout'),
    path('pay/<str:order_code>/proof/', pay_views.upload_proof_view, name='payment-proof-upload'),
    path('pay/<str:order_code>/simulate-proof/', pay_views.simulate_test_proof_view, name='payment-simulate-proof'),
    path('status/<str:registration_code>/', reg_views.registration_status_view, name='registration-status'),
    path('pass/<str:pass_code>/', reg_views.attendee_badge_view, name='attendee-badge'),
    path('pass/<str:pass_code>/send-email/', reg_views.send_pass_email_view, name='send-pass-email'),

    # Admin Operations Dashboard
    path('dashboard/', include('apps.dashboard.urls')),

    # Partner REST API (v1)
    path('api/v1/', include('apps.api_v1.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
