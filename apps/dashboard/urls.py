from django.urls import path
from . import views
from . import auth_views

urlpatterns = [
    path('login/', auth_views.login_view, name='dashboard-login'),
    path('logout/', auth_views.logout_view, name='dashboard-logout'),
    path('session/ping/', auth_views.session_ping_view, name='dashboard-session-ping'),
    path('', views.overview_dashboard_view, name='dashboard-overview'),
    path('tenant/switch/<int:tenant_id>/', views.tenant_switch_view, name='dashboard-tenant-switch'),
    path('events/', views.events_list_view, name='dashboard-events-list'),
    path('events/create/', views.create_event_view, name='dashboard-event-create'),
    path('events/<int:event_id>/', views.event_detail_view, name='dashboard-event-detail'),
    path('events/<int:event_id>/edit/', views.edit_event_view, name='dashboard-event-edit'),
    path('events/<int:event_id>/delete/', views.delete_event_view, name='dashboard-event-delete'),
    path('events/<int:event_id>/form/', views.form_builder_view, name='dashboard-event-form'),
    path('forms/', views.forms_list_view, name='dashboard-forms-list'),
    path('forms/<int:event_id>/', views.form_builder_view, name='dashboard-form-detail'),
    path('events/<int:event_id>/export-csv/', views.export_attendees_csv, name='dashboard-event-export-csv'),
    path('verification-queue/', views.manual_verification_queue_view, name='dashboard-verification-queue'),
    path('verification-queue/bulk-action/', views.verification_bulk_action_view, name='dashboard-verification-bulk-action'),
    path('verification-queue/<int:verification_id>/action/', views.verification_action_view, name='dashboard-verification-action'),
    path('verification-queue/<int:verification_id>/delete-image/', views.delete_payment_image_view, name='dashboard-verification-delete-image'),
    path('registrations/', views.registrations_list_view, name='dashboard-registrations-list'),
    path('registrations/<str:registration_code>/send-email/', views.send_registration_email_view, name='dashboard-registration-send-email'),
    path('emails/', views.email_logs_view, name='dashboard-email-logs'),
    path('emails/<int:email_id>/preview/', views.email_preview_view, name='dashboard-email-preview'),
    path('emails/<int:email_id>/resend/', views.resend_email_log_view, name='dashboard-email-resend'),
    path('audit/', views.audit_logs_view, name='dashboard-audit-logs'),
]
