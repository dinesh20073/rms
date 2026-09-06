import os
import django
from decimal import Decimal
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_core.settings')
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone
from apps.tenants.models import Tenant, ApiKey
from apps.events.models import Event
from apps.forms_builder.models import Form, FormField
from apps.registrations.models import Customer, Registration, Attendee
from apps.payments.models import Order, Payment
from apps.verification.models import Verification, PaymentEvidence
from apps.notifications.services import send_registration_success_email
from apps.audit.services import log_audit_event

def seed():
    print(">> Seeding EMS Platform Database...")

    # 1. Admin User
    admin_user, created = User.objects.get_or_create(username='admin')
    if created:
        admin_user.set_password('admin123')
        admin_user.is_superuser = True
        admin_user.is_staff = True
        admin_user.email = 'admin@ems-platform.com'
        admin_user.save()
        print("  [+] Created Admin User (admin / admin123)")

    # 2. Tenants
    tenant1, _ = Tenant.objects.get_or_create(
        slug='acme-tech',
        defaults={'name': 'Acme Global Events', 'domain': 'events.acmetech.com'}
    )
    tenant2, _ = Tenant.objects.get_or_create(
        slug='hyper-scale',
        defaults={'name': 'HyperScale Conferences', 'domain': 'hyperscale.io'}
    )
    print("  [+] Created Organizations: Acme Global Events, HyperScale Conferences")

    # 3. API Keys
    api_key, _ = ApiKey.objects.get_or_create(
        tenant=tenant1,
        name='Production Partner Key',
        defaults={'key': 'ems_live_8f7b2c91a0e4d6f83b2a1c9e8d7f6a5b'}
    )

    # 4. Events
    event1, _ = Event.objects.get_or_create(
        tenant=tenant1,
        slug='tech-conference-2026',
        defaults={
            'event_code': 'EVT-2026-0001',
            'title': 'Tech Conference 2026',
            'description': 'Annual flagship technology conference covering AI, Cloud Architectures, and Scalable Systems.',
            'registration_fee': Decimal('500.00'),
            'currency': 'INR',
            'upi_id': 'dinesh.b@superyes',
            'upi_name': 'Dinesh',
            'venue': 'Bengaluru International Exhibition Centre (BIEC) & Online',
            'status': 'OPEN',
            'max_capacity': 2500
        }
    )

    event2, _ = Event.objects.get_or_create(
        tenant=tenant1,
        slug='ai-innovators-summit-2026',
        defaults={
            'event_code': 'EVT-2026-0002',
            'title': 'AI Innovators Summit 2026',
            'description': 'Deep dive into Generative AI, Large Language Models, and Agentic Workflows.',
            'registration_fee': Decimal('1200.00'),
            'currency': 'INR',
            'upi_id': 'dinesh.b@superyes',
            'upi_name': 'Dinesh',
            'venue': 'Auditorium A, HITEC City, Hyderabad',
            'status': 'OPEN',
            'max_capacity': 1000
        }
    )

    # 5. Form Builder Initialization
    form1, _ = Form.objects.get_or_create(event=event1, title='Tech Conference 2026 Registration')
    form1.create_default_fields()

    form2, _ = Form.objects.get_or_create(event=event2, title='AI Innovators Summit Registration')
    form2.create_default_fields()
    print("  [+] Initialized Dynamic Form Builders")

    # 6. Sample Customers & Registrations
    sample_data = [
        {
            'name': 'Dinesh Kumar',
            'email': 'dinesh@example.com',
            'phone': '+91 98765 43210',
            'company': 'Tech Corp India',
            'designation': 'Lead Architect',
            'status': 'COMPLETED',
            'order_status': 'VERIFIED',
            'txn_id': '423891029481',
            'event': event1
        },
        {
            'name': 'Priya Sharma',
            'email': 'priya.sharma@innovate.org',
            'phone': '+91 91234 56789',
            'company': 'Innovate AI Labs',
            'designation': 'Senior ML Engineer',
            'status': 'COMPLETED',
            'order_status': 'VERIFIED',
            'txn_id': '839201948271',
            'event': event1
        },
        {
            'name': 'Ankit Verma',
            'email': 'ankit.v@fintechcloud.com',
            'phone': '+91 98231 44556',
            'company': 'Fintech Cloud',
            'designation': 'Product Lead',
            'status': 'MANUAL_REVIEW',
            'order_status': 'MANUAL_REVIEW',
            'txn_id': '123456789012',
            'event': event1,
            'review_notes': 'Amount mismatch: Expected ₹500.00, Extracted ₹450.00 from blurred receipt.'
        },
        {
            'name': 'Rohan Mehta',
            'email': 'rohan@startuply.io',
            'phone': '+91 99887 76655',
            'company': 'Startuply',
            'designation': 'Founder & CEO',
            'status': 'COMPLETED',
            'order_status': 'VERIFIED',
            'txn_id': '948201938572',
            'event': event2
        }
    ]

    for item in sample_data:
        ev = item['event']
        cust, _ = Customer.objects.get_or_create(
            tenant=ev.tenant,
            email=item['email'],
            defaults={
                'name': item['name'],
                'phone': item['phone'],
                'company': item['company'],
                'designation': item['designation']
            }
        )

        reg, reg_created = Registration.objects.get_or_create(
            event=ev,
            customer=cust,
            defaults={
                'amount': ev.registration_fee,
                'status': item['status'],
                'form_responses': {
                    'Full Name': item['name'],
                    'Email': item['email'],
                    'Phone': item['phone'],
                    'Company': item['company'],
                    'Designation': item['designation']
                }
            }
        )

        order, order_created = Order.objects.get_or_create(
            registration=reg,
            defaults={
                'amount': ev.registration_fee,
                'currency': ev.currency,
                'status': item['order_status']
            }
        )

        if item['status'] == 'COMPLETED':
            Attendee.objects.get_or_create(registration=reg)
            Payment.objects.get_or_create(
                order=order,
                transaction_id=item['txn_id'],
                defaults={
                    'amount': order.amount,
                    'currency': order.currency,
                    'payer_name': cust.name,
                    'payee_upi': ev.upi_id,
                    'status': 'SUCCESS'
                }
            )
            Verification.objects.get_or_create(
                order=order,
                defaults={
                    'decision': 'AUTO_VERIFIED',
                    'is_amount_matched': True,
                    'is_txn_id_found': True,
                    'ocr_amount': order.amount,
                    'ocr_transaction_id': item['txn_id'],
                    'ocr_payee': ev.upi_name,
                    'review_notes': 'Auto-verified by AI OCR and verification rules.'
                }
            )
            send_registration_success_email(reg)

        elif item['status'] == 'MANUAL_REVIEW':
            Verification.objects.get_or_create(
                order=order,
                defaults={
                    'decision': 'MANUAL_REVIEW',
                    'is_amount_matched': False,
                    'is_txn_id_found': True,
                    'ocr_amount': Decimal('450.00'),
                    'ocr_transaction_id': item['txn_id'],
                    'ocr_payee': ev.upi_name,
                    'review_notes': item.get('review_notes', 'Needs manual review')
                }
            )

        log_audit_event('REGISTRATION_CREATED', reg.registration_code, {'customer': cust.email, 'event': ev.title}, tenant=ev.tenant)

    print("  [+] Created Sample Registrations, Orders, Attendee Passes, and Emails")
    print("\n[SUCCESS] Database Seeding Completed Successfully!")

if __name__ == '__main__':
    seed()
