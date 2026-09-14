from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q

from apps.verification.models import Verification
from apps.verification.engine import VerificationEngine
from apps.audit.services import log_audit_event
from apps.dashboard.views.overview import get_current_tenant


@login_required(login_url='login')
def manual_verification_queue_view(request):
    tenant = get_current_tenant(request)
    verifications_qs = Verification.objects.filter(order__registration__event__tenant=tenant)
    
    queue = list(verifications_qs.filter(
        decision='MANUAL_REVIEW'
    ).select_related('order', 'order__registration', 'order__registration__customer', 'order__registration__event', 'evidence').order_by('-created_at'))

    counts = verifications_qs.aggregate(
        manual_approved=Count('id', filter=Q(decision='MANUAL_APPROVED')),
        rejected=Count('id', filter=Q(decision='REJECTED'))
    )
    manual_approved_count = counts['manual_approved'] or 0
    rejected_count = counts['rejected'] or 0
    total_processed = manual_approved_count + rejected_count
    approval_rate = round((manual_approved_count / max(total_processed, 1)) * 100, 1) if total_processed > 0 else 100.0

    recent_history = list(verifications_qs.exclude(
        decision='MANUAL_REVIEW'
    ).select_related('order', 'order__registration', 'order__registration__customer', 'order__registration__event', 'reviewed_by', 'evidence').order_by('-reviewed_at', '-created_at')[:25])

    return render(request, 'dashboard/verification/queue.html', {
        'queue': queue,
        'recent_history': recent_history,
        'manual_approved_count': manual_approved_count,
        'rejected_count': rejected_count,
        'total_processed': total_processed,
        'approval_rate': approval_rate,
        'tenant': tenant
    })


@login_required(login_url='login')
def delete_payment_image_view(request, verification_id):
    if request.method != 'POST':
        return redirect('dashboard-verification-queue')

    tenant = get_current_tenant(request)
    verification = get_object_or_404(Verification, id=verification_id, order__registration__event__tenant=tenant)
    
    if verification.evidence:
        evidence = verification.evidence
        order_code = verification.order.order_code
        
        if evidence.screenshot:
            try:
                evidence.screenshot.delete(save=False)
            except Exception:
                pass
            evidence.screenshot = None
            
        evidence.image_base64 = ''
        evidence.save()
        
        log_audit_event(
            action='PAYMENT_IMAGE_DELETED',
            reference_id=order_code,
            details={'verification_id': verification.id, 'order_code': order_code},
            tenant=tenant,
            actor=request.user.username if request.user else 'Admin'
        )
        messages.success(request, f"Payment proof image for order {order_code} has been deleted.")
    else:
        messages.info(request, "No proof image found to delete.")

    return redirect(request.META.get('HTTP_REFERER', 'dashboard-verification-queue'))


@login_required(login_url='login')
def verification_action_view(request, verification_id):
    if request.method != 'POST':
        return redirect('dashboard-verification-queue')

    tenant = get_current_tenant(request)
    verification = get_object_or_404(Verification, id=verification_id, order__registration__event__tenant=tenant)
    action = request.POST.get('action')
    notes = request.POST.get('notes', '').strip()

    user = request.user if request.user.is_authenticated else None

    if action == 'APPROVE':
        VerificationEngine.manual_approve(verification.order, reviewer_user=user, notes=notes or 'Approved by admin review')
        messages.success(request, f"Order {verification.order.order_code} has been approved and marked as Payment Received!")
    elif action == 'REJECT':
        VerificationEngine.manual_reject(verification.order, reviewer_user=user, notes=notes or 'Rejected by Admin')
        messages.warning(request, f"Order {verification.order.order_code} has been marked as Not Received.")
    elif action == 'DELETE':
        order_code = verification.order.order_code
        log_audit_event(
            action='VERIFICATION_LOG_DELETED',
            reference_id=order_code,
            details={'verification_id': verification.id, 'decision': verification.decision},
            tenant=tenant,
            actor=user.username if user else 'Admin'
        )
        verification.delete()
        messages.success(request, f"Verification log for order {order_code} has been deleted.")
    elif action == 'DELETE_IMAGE':
        if verification.evidence:
            if verification.evidence.screenshot:
                try:
                    verification.evidence.screenshot.delete(save=False)
                except Exception:
                    pass
                verification.evidence.screenshot = None
            verification.evidence.image_base64 = ''
            verification.evidence.save()
            log_audit_event('PAYMENT_IMAGE_DELETED', verification.order.order_code, {'verification_id': verification.id}, tenant=tenant, actor=user.username if user else 'Admin')
            messages.success(request, f"Payment proof image for order {verification.order.order_code} has been deleted.")

    return redirect('dashboard-verification-queue')


@login_required(login_url='login')
def verification_bulk_action_view(request):
    if request.method != 'POST':
        return redirect('dashboard-verification-queue')

    tenant = get_current_tenant(request)
    action = request.POST.get('action')
    ids_raw = request.POST.getlist('selected_ids')
    if not ids_raw:
        val = request.POST.get('selected_ids', '')
        ids_raw = [val] if val else []
    
    verification_ids = []
    for raw_id in ids_raw:
        if isinstance(raw_id, str):
            for part in raw_id.split(','):
                part = part.strip()
                if part.isdigit():
                    verification_ids.append(int(part))

    if not verification_ids:
        messages.warning(request, "No verification logs selected.")
        return redirect('dashboard-verification-queue')

    verifications = list(Verification.objects.filter(
        id__in=verification_ids,
        order__registration__event__tenant=tenant
    ).select_related('order', 'order__registration', 'order__registration__event', 'evidence'))

    user = request.user if request.user.is_authenticated else None
    count = len(verifications)

    if count == 0:
        messages.warning(request, "Selected logs were not found.")
        return redirect('dashboard-verification-queue')

    if action == 'APPROVE':
        for v in verifications:
            VerificationEngine.manual_approve(v.order, reviewer_user=user, notes=notes or 'Bulk approved by admin')
        messages.success(request, f"Successfully marked {count} order(s) as Payment Received.")
    elif action == 'REJECT':
        for v in verifications:
            VerificationEngine.manual_reject(v.order, reviewer_user=user, notes=notes or 'Rejected by Admin')
        messages.warning(request, f"Successfully marked {count} order(s) as Not Received.")
    elif action == 'DELETE':
        for v in verifications:
            log_audit_event(
                action='VERIFICATION_LOG_DELETED',
                reference_id=v.order.order_code,
                details={'verification_id': v.id, 'decision': v.decision},
                tenant=tenant,
                actor=user.username if user else 'Admin'
            )
            v.delete()
        messages.success(request, f"Successfully deleted {count} verification log(s).")
    elif action == 'DELETE_IMAGE':
        deleted_count = 0
        for v in verifications:
            if v.evidence and (v.evidence.image_base64 or v.evidence.screenshot):
                if v.evidence.screenshot:
                    try:
                        v.evidence.screenshot.delete(save=False)
                    except Exception:
                        pass
                    v.evidence.screenshot = None
                v.evidence.image_base64 = ''
                v.evidence.save()
                deleted_count += 1
                log_audit_event('PAYMENT_IMAGE_DELETED', v.order.order_code, {'verification_id': v.id}, tenant=tenant, actor=user.username if user else 'Admin')
        messages.success(request, f"Successfully purged payment proof images for {deleted_count} record(s).")
    else:
        messages.error(request, "Invalid action requested.")

    return redirect('dashboard-verification-queue')


@login_required(login_url='login')
def view_payment_proof_image(request, order_code):
    import base64
    from django.http import HttpResponse, Http404

    tenant = get_current_tenant(request)
    verification = Verification.objects.filter(
        order__order_code=order_code,
        order__registration__event__tenant=tenant
    ).select_related('evidence', 'order').first()

    if not verification or not verification.evidence:
        raise Http404("Payment proof not found")

    evidence = verification.evidence
    if evidence.image_base64:
        try:
            raw_val = evidence.image_base64
            if ',' in raw_val:
                header, data = raw_val.split(',', 1)
                mime = header.split(';')[0].replace('data:', '') or 'image/png'
            else:
                mime = 'image/png'
                data = raw_val
            raw_bytes = base64.b64decode(data)
            response = HttpResponse(raw_bytes, content_type=mime)
            response['Content-Disposition'] = f'inline; filename="receipt_{order_code}.png"'
            return response
        except Exception:
            pass

    if evidence.screenshot:
        try:
            content_file = evidence.screenshot.open('rb')
            return HttpResponse(content_file.read(), content_type='image/png')
        except Exception:
            pass

    raise Http404("No image data available for this payment")
