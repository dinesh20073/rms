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
    path('favicon.ico', lambda req: HttpResponse(status=204)),
    path('admin/', admin.site.urls),
    
    # Secure Authentication
    path('login/', auth_views.login_view, name='login'),
    path('logout/', auth_views.logout_view, name='logout'),
    
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

from django.urls import re_path
from django.views.static import serve

urlpatterns += [
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATICFILES_DIRS[0]}),
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
