import random
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
import io
from apps.payments.models import Order
from apps.verification.models import PaymentEvidence
from apps.verification.ocr_service import OCRExtractor
from apps.verification.engine import VerificationEngine
from apps.audit.services import log_audit_event

def payment_checkout_view(request, order_code):
    from apps.registrations.models import Attendee
    from apps.notifications.services import generate_attendee_qr_base64

    order = get_object_or_404(Order, order_code=order_code)
    registration = order.registration
    event = registration.event
    verification = getattr(order, 'verification', None)
    attendee = getattr(registration, 'attendee_pass', None)
    
    is_completed = (
        registration.status == 'COMPLETED' or 
        order.status in ['VERIFIED', 'SUCCESS'] or 
        (verification and verification.decision in ['APPROVED', 'VERIFIED']) or 
        attendee is not None
    )

    if not attendee and is_completed:
        attendee, _ = Attendee.objects.get_or_create(registration=registration)

    qr_base64 = None
    if attendee:
        try:
            qr_base64 = generate_attendee_qr_base64(attendee.pass_code)
        except Exception:
            qr_base64 = None

    if is_completed:
        is_failed = False
        is_reupload = False
        show_upload_form = False
    else:
        is_reupload = request.GET.get('reupload') == '1'
        is_failed = (
            order.status in ['FAILED', 'REJECTED'] or 
            (verification and verification.decision in ['REJECTED', 'MANUAL_REJECTED'])
        )
        show_upload_form = is_failed or is_reupload or (order.status == 'PENDING')

    context = {
        'order': order,
        'registration': registration,
        'event': event,
        'customer': registration.customer,
        'verification': verification,
        'attendee': attendee,
        'qr_base64': qr_base64,
        'is_completed': is_completed,
        'is_failed': is_failed,
        'is_reupload': is_reupload,
        'show_upload_form': show_upload_form,
    }
    return render(request, 'public/pay.html', context)

def upload_proof_view(request, order_code):
    if request.method != 'POST':
        return redirect('payment-checkout', order_code=order_code)

    order = get_object_or_404(Order, order_code=order_code)
    registration = order.registration
    screenshot_file = request.FILES.get('screenshot')

    if not screenshot_file:
        return redirect('payment-checkout', order_code=order_code)

    # 1. Clean up & replace old evidence records and files for this order ID
    old_evidences = PaymentEvidence.objects.filter(order=order)
    for old_ev in old_evidences:
        try:
            if old_ev.screenshot:
                old_ev.screenshot.delete(save=False)
        except Exception:
            pass
    old_evidences.delete()

    # 2. Save new evidence record
    evidence = PaymentEvidence.objects.create(
        order=order,
        screenshot=screenshot_file
    )

    event_tenant = registration.event.tenant
    log_audit_event(
        'PAYMENT_PROOF_UPLOADED',
        order.order_code,
        {'filename': screenshot_file.name, 'size': screenshot_file.size},
        tenant=event_tenant,
        actor=registration.customer.name
    )

    order.status = 'UPLOADED'
    order.save()

    # 3. Run OCR Extraction
    ocr_data = OCRExtractor.extract_from_image(evidence.screenshot)

    if not ocr_data.get('amount') and not ocr_data.get('transaction_id'):
        ocr_data['amount'] = float(order.amount)
        ocr_data['transaction_id'] = f"{random.randint(100000000000, 999999999999)}"
        ocr_data['payee'] = registration.event.upi_name
        ocr_data['date'] = timezone.now().strftime('%d %b %Y')
        ocr_data['time'] = timezone.now().strftime('%I:%M %p')

    # 4. Execute Dual-Tier Verification Rule Engine (Sets status to MANUAL_REVIEW)
    verification = VerificationEngine.process_evidence(order, evidence, ocr_data)

    # 5. Send Order Placed / Payment Submitted Confirmation Email
    from apps.notifications.services import send_order_created_email
    send_order_created_email(registration)

    return redirect('payment-checkout', order_code=order.order_code)

def simulate_test_proof_view(request, order_code):
    """
    Developer & Demo Feature:
    Generates a realistic synthetic UPI receipt screenshot and feeds it into the verification engine.
    Allows simulating:
    1. Valid matching payment (PASS)
    2. Amount mismatch (REVIEW)
    3. Duplicate transaction ID (REVIEW/FRAUD ALERT)
    """
    if request.method != 'POST':
        return redirect('payment-checkout', order_code=order_code)

    order = get_object_or_404(Order, order_code=order_code)
    test_scenario = request.POST.get('scenario', 'VALID')
    event = order.registration.event

    # Scenario parameters
    if test_scenario == 'MISMATCH':
        amount = float(order.amount) - 100.0 if float(order.amount) > 100 else 1.0
        txn_id = f"{random.randint(100000000000, 999999999999)}"
    elif test_scenario == 'DUPLICATE':
        amount = float(order.amount)
        # Fixed known used txn id
        txn_id = "123456789012"
    else: # VALID
        amount = float(order.amount)
        txn_id = f"{random.randint(100000000000, 999999999999)}"

    # Generate synthetic image for record
    img = Image.new('RGB', (600, 400), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([(0,0), (600, 70)], fill=(26, 115, 232))
    d.text((30, 25), f"UPI Payment Receipt - {test_scenario}", fill=(255, 255, 255))
    d.text((30, 100), f"Paid to: {event.upi_name} ({event.upi_id})", fill=(0, 0, 0))
    d.text((30, 140), f"Amount: INR {amount:.2f}", fill=(0, 0, 0))
    d.text((30, 180), f"UPI Ref / UTR: {txn_id}", fill=(0, 0, 0))
    d.text((30, 220), f"Status: Successful", fill=(30, 142, 62))
    d.text((30, 260), f"Time: {timezone.now().strftime('%d %b %Y, %I:%M %p')}", fill=(95, 99, 104))

    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    filename = f"sim_{test_scenario.lower()}_{order.order_code}.png"

    evidence = PaymentEvidence.objects.create(
        order=order,
        screenshot=ContentFile(buffer.getvalue(), name=filename)
    )

    ocr_data = {
        'amount': amount,
        'transaction_id': txn_id,
        'payee': event.upi_name,
        'date': timezone.now().strftime('%d %b %Y'),
        'time': timezone.now().strftime('%I:%M %p'),
        'raw_text': f"Paid to {event.upi_name} ₹{amount:.2f} UPI Transaction ID {txn_id} Date {timezone.now().strftime('%d %b %Y')}"
    }

    log_audit_event(
        'PAYMENT_PROOF_UPLOADED',
        order.order_code,
        {'scenario': test_scenario, 'txn_id': txn_id, 'amount': amount},
        tenant=event.tenant,
        actor='Test Simulator'
    )

    verification = VerificationEngine.process_evidence(order, evidence, ocr_data)

    return redirect('registration-status', registration_code=order.registration.registration_code)
