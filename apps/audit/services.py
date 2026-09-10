from apps.audit.models import AuditLog

def log_audit_event(action, reference_id='', details=None, tenant=None, actor='System', ip_address=None):
    """
    Log an event to the audit trail with fail-safe error handling.
    """
    if details is None:
        details = {}
    try:
        return AuditLog.objects.create(
            tenant=tenant,
            actor=actor,
            action=action,
            reference_id=reference_id,
            details=details,
            ip_address=ip_address
        )
    except Exception as e:
        print(f"Audit log warning: {e}")
        return None

