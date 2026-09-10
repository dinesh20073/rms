from decimal import Decimal
from django.utils import timezone
from apps.payments.models import Order, Payment
from apps.registrations.models import Registration, Attendee
from apps.verification.models import Verification, PaymentEvidence
from apps.audit.services import log_audit_event
from apps.notifications.services import send_registration_success_email

class VerificationEngine:
    """
    Dual-Tier Verification Engine:
    1. Structured OCR Extractor
    2. Django Rule Engine & Duplicate Fraud Protection
    """

    @classmethod
    def process_evidence(cls, order, evidence, ocr_data, user=None):
        tenant = order.registration.event.tenant
        event = order.registration.event
        registration = order.registration

        log_audit_event('OCR_STARTED', order.order_code, {'evidence_id': evidence.id}, tenant=tenant)

        # Store extracted data
        evidence.extracted_data = ocr_data
        evidence.raw_ocr_text = ocr_data.get('raw_text', '')
        evidence.save()

        log_audit_event('OCR_COMPLETED', order.order_code, ocr_data, tenant=tenant)

        # Rule evaluation variables
        ocr_amount_val = ocr_data.get('amount')
        ocr_txn_id = ocr_data.get('transaction_id')
        ocr_payee = ocr_data.get('payee')
        ocr_timestamp_str = f"{ocr_data.get('date', '')} {ocr_data.get('time', '')}".strip()

        is_amount_matched = False
        is_txn_id_found = bool(ocr_txn_id and len(str(ocr_txn_id).strip()) >= 6)
        is_duplicate_txn = False
        is_payee_matched = False
        review_notes_list = []

        # 1. Amount Match Check (Assistant note for human reviewer)
        if ocr_amount_val is not None:
            try:
                ocr_dec = Decimal(str(ocr_amount_val))
                if abs(ocr_dec - order.amount) < Decimal('0.01'):
                    is_amount_matched = True
                    review_notes_list.append(f"Amount match confirmed: ₹{ocr_dec}")
                else:
                    review_notes_list.append(f"⚠️ Amount mismatch: Expected ₹{order.amount}, Extracted ₹{ocr_dec}")
            except Exception as e:
                review_notes_list.append(f"Invalid amount format in OCR: {e}")
        else:
            review_notes_list.append("Could not extract payment amount from receipt")

        # 2. Transaction ID & Duplicate Fraud Protection Check (Assistant note for human reviewer)
        if is_txn_id_found:
            clean_txn_id = str(ocr_txn_id).strip()
            # Check if this transaction ID was previously approved on ANY other order
            existing_payment = Payment.objects.filter(transaction_id=clean_txn_id).exclude(order=order).first()
            existing_verification = Verification.objects.filter(
                ocr_transaction_id=clean_txn_id, 
                decision__in=['AUTO_VERIFIED', 'MANUAL_APPROVED']
            ).exclude(order=order).first()

            if existing_payment or existing_verification:
                is_duplicate_txn = True
                conflict_order = existing_payment.order.order_code if existing_payment else existing_verification.order.order_code
                review_notes_list.append(f"⚠️ DUPLICATE TRANSACTION DETECTED: UTR {clean_txn_id} was already used for order {conflict_order}!")
            else:
                review_notes_list.append(f"UTR: {clean_txn_id}")
        else:
            review_notes_list.append("Standard 12-digit UTR not detected - verify screenshot manually")

        # 3. Payee Match Check
        if ocr_payee and (event.upi_name.lower() in ocr_payee.lower() or event.upi_id.lower() in ocr_payee.lower()):
            is_payee_matched = True

        # Save verification record with extracted assistant notes
        verification, _ = Verification.objects.get_or_create(order=order)
        verification.evidence = evidence
        verification.is_amount_matched = is_amount_matched
        verification.is_duplicate_txn = is_duplicate_txn
        verification.is_txn_id_found = is_txn_id_found
        verification.is_payee_matched = is_payee_matched
        verification.ocr_amount = ocr_amount_val if ocr_amount_val is not None else None
        verification.ocr_transaction_id = ocr_txn_id or ''
        verification.ocr_payee = ocr_payee or ''
        verification.ocr_timestamp_str = ocr_timestamp_str

        # STRICT HUMAN VERIFICATION ONLY: All uploaded proofs are queued for manual human decision
        verification.decision = 'MANUAL_REVIEW'
        verification.review_notes = " | ".join(review_notes_list) if review_notes_list else "Awaiting human admin review."
        verification.save()

        order.status = 'MANUAL_REVIEW'
        order.save()
        registration.status = 'MANUAL_REVIEW'
        registration.save()

        log_audit_event('PAYMENT_QUEUED_FOR_HUMAN_REVIEW', order.order_code, {
            'reasons': review_notes_list,
            'amount_matched': is_amount_matched,
            'txn_id': ocr_txn_id
        }, tenant=tenant)

        return verification

    @classmethod
    def complete_registration(cls, registration, tenant=None):
        if not tenant:
            tenant = registration.event.tenant

        log_audit_event('REGISTRATION_STARTED', registration.registration_code, {}, tenant=tenant)

        # Transition status
        registration.status = 'COMPLETED'
        registration.save()

        # Provision Attendee Pass
        Attendee.objects.get_or_create(registration=registration)

        log_audit_event('REGISTRATION_SUCCESS', registration.registration_code, {'customer': registration.customer.email}, tenant=tenant)

        # Send confirmation email
        send_registration_success_email(registration)

    @classmethod
    def manual_approve(cls, order, reviewer_user, notes='Manually approved by admin'):
        tenant = order.registration.event.tenant
        registration = order.registration

        verification, _ = Verification.objects.get_or_create(order=order)
        verification.decision = 'MANUAL_APPROVED'
        verification.reviewed_by = reviewer_user
        verification.reviewed_at = timezone.now()
        verification.review_notes = notes
        verification.save()

        order.status = 'VERIFIED'
        order.save()

        # Ensure Payment record
        txn_id = verification.ocr_transaction_id or f"MANUAL-{order.order_code}"
        Payment.objects.get_or_create(
            order=order,
            transaction_id=txn_id,
            defaults={
                'amount': order.amount,
                'currency': order.currency,
                'payee_upi': order.registration.event.upi_id,
                'payer_name': registration.customer.name,
                'status': 'SUCCESS'
            }
        )

        log_audit_event('PAYMENT_MANUAL_APPROVED', order.order_code, {'reviewer': reviewer_user.username if reviewer_user else 'Admin'}, tenant=tenant, actor=reviewer_user.username if reviewer_user else 'Admin')
        
        cls.complete_registration(registration, tenant=tenant)
        return verification

    @classmethod
    def manual_reject(cls, order, reviewer_user, notes='Rejected during verification'):
        tenant = order.registration.event.tenant
        registration = order.registration

        verification, _ = Verification.objects.get_or_create(order=order)
        verification.decision = 'REJECTED'
        verification.reviewed_by = reviewer_user
        verification.reviewed_at = timezone.now()
        verification.review_notes = notes
        verification.save()

        order.status = 'FAILED'
        order.save()
        registration.status = 'FAILED'
        registration.save()

        log_audit_event('PAYMENT_REJECTED', order.order_code, {'reason': notes}, tenant=tenant, actor=reviewer_user.username if reviewer_user else 'Admin')

        # Trigger failed payment notification email
        from apps.notifications.services import send_payment_rejected_email
        send_payment_rejected_email(registration, reason=notes)

        return verification
