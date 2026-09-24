# Dashboard views package — modular split of the original monolithic views.py
# All views are re-exported here for backward compatibility with urls.py imports

from apps.dashboard.views.overview import (
    get_current_tenant,
    filter_registrations_queryset,
    overview_dashboard_view,
    tenant_switch_view,
)

from apps.dashboard.views.events import (
    events_list_view,
    create_event_view,
    event_detail_view,
    edit_event_view,
    delete_event_view,
)

from apps.dashboard.views.forms import (
    forms_list_view,
    form_builder_view,
)

from apps.dashboard.views.registrations import (
    registrations_list_view,
    export_attendees_csv,
    send_registration_email_view,
    change_registration_status_view,
    registration_bulk_action_view,
)

from apps.dashboard.views.verification import (
    manual_verification_queue_view,
    verification_action_view,
    verification_bulk_action_view,
    delete_payment_image_view,
    view_payment_proof_image,
)

from apps.dashboard.views.emails import (
    email_logs_view,
    email_preview_view,
    resend_email_log_view,
)

from apps.dashboard.views.audit import (
    audit_logs_view,
)

from apps.dashboard.views.revenue import (
    revenue_analytics_view,
)

from apps.dashboard.views.partner import (
    partner_api_view,
)

from apps.dashboard.views.database import (
    database_view,
    export_customers_csv,
)

from apps.dashboard.views.scanner import (
    scanner_page_view,
    scanner_verify_api,
    scanner_stats_api,
    scanner_resend_email_api,
)
