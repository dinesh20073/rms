import os
import django
from decimal import Decimal
from datetime import timedelta

def seed():
    if not os.environ.get('DJANGO_SETTINGS_MODULE'):
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_core.settings')
    try:
        django.setup()
    except Exception:
        pass

    from django.contrib.auth.models import User
    from django.utils import timezone
    from apps.tenants.models import Tenant, ApiKey
    from apps.events.models import Event
    from apps.forms_builder.models import Form, FormField
    from apps.registrations.models import Customer, Registration, Attendee
    from apps.payments.models import Order, Payment
    from apps.verification.models import Verification, PaymentEvidence
    from apps.notifications.models import EmailLog
    from apps.audit.services import log_audit_event

    print(">> Seeding Comprehensive EMS Platform Sample Data...")

    # 1. Admin Users with constant deterministic hashes (preserves session hash across serverless lambda containers)
    ADMIN_HASH = 'pbkdf2_sha256$1200000$TkfTgMExkiowwzK7VuKLfA$MT1/b74TKiNxd+R8ImzC3Mtj1u4Oy+dUwLNYlaxXFOc='
    NIZHAL_HASH = 'pbkdf2_sha256$1200000$y375MNroI33LpWK39JlIfM$rlyDj8UzJMv4lLkugrKB/n9N4UvAOerk25OjghszwZE='

    nizhal_user, _ = User.objects.get_or_create(username='Nizhal')
    nizhal_user.password = NIZHAL_HASH
    nizhal_user.is_superuser = True
    nizhal_user.is_staff = True
    nizhal_user.first_name = 'Nizhal'
    nizhal_user.last_name = 'Admin'
    nizhal_user.email = 'nizhalcommunity@gmail.com'
    nizhal_user.save()

    admin_user, _ = User.objects.get_or_create(username='admin')
    admin_user.password = ADMIN_HASH
    admin_user.is_superuser = True
    admin_user.is_staff = True
    admin_user.email = 'nizhalcommunity@gmail.com'
    admin_user.save()
    print("  [+] Configured Superusers 'Nizhal' and 'admin'")

    # 2. Tenants
    tenant1, _ = Tenant.objects.get_or_create(
        slug='acme-tech',
        defaults={'name': 'Acme Global Events', 'domain': 'events.acmetech.com'}
    )
    tenant2, _ = Tenant.objects.get_or_create(
        slug='hyper-scale',
        defaults={'name': 'HyperScale Conferences', 'domain': 'hyperscale.io'}
    )
    print("  [+] Organizations: Acme Global Events, HyperScale Conferences")

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

    event3, _ = Event.objects.get_or_create(
        tenant=tenant1,
        slug='cloud-devops-summit-2026',
        defaults={
            'event_code': 'EVT-2026-0003',
            'title': 'Cloud & DevOps Summit 2026',
            'description': 'Modern Kubernetes, Serverless architectures, Platform Engineering & SRE best practices.',
            'registration_fee': Decimal('750.00'),
            'currency': 'INR',
            'upi_id': 'dinesh.b@superyes',
            'upi_name': 'Dinesh',
            'venue': 'ITC Grand Chola, Chennai',
            'status': 'OPEN',
            'max_capacity': 800
        }
    )

    event4, _ = Event.objects.get_or_create(
        tenant=tenant1,
        slug='product-design-ux-bootcamp',
        defaults={
            'event_code': 'EVT-2026-0004',
            'title': 'Product Design & UX Bootcamp',
            'description': 'Hands-on interactive design systems, Figma masterclass, and user research sprint.',
            'registration_fee': Decimal('350.00'),
            'currency': 'INR',
            'upi_id': 'dinesh.b@superyes',
            'upi_name': 'Dinesh',
            'venue': 'Virtual Live Workshop (Zoom Pro)',
            'status': 'OPEN',
            'max_capacity': 500
        }
    )

    # 5. Forms
    for ev in [event1, event2, event3, event4]:
        f, _ = Form.objects.get_or_create(
            event=ev,
            defaults={'title': f'{ev.title} Registration'}
        )
        f.create_default_fields()

    # 6. Sample Registrations & Attendees
    sample_data = [
        {
            'name': 'Dinesh Kumar',
            'email': 'dinesh.k@example.com',
            'phone': '+91 98765 43210',
            'company': 'Nizhal Tech Systems',
            'designation': 'Lead Architect',
            'status': 'COMPLETED',
            'order_status': 'VERIFIED',
            'txn_id': '423891029481',
            'event': event1,
            'email_status': 'SENT'
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
            'event': event1,
            'email_status': 'SENT'
        },
        {
            'name': 'Ankit Verma',
            'email': 'ankit.v@fintechcloud.com',
            'phone': '+91 98231 44556',
            'company': 'Fintech Cloud Ltd',
            'designation': 'Product Lead',
            'status': 'MANUAL_REVIEW',
            'order_status': 'MANUAL_REVIEW',
            'txn_id': '123456789012',
            'event': event1,
            'review_notes': 'Amount mismatch: Expected ₹500.00, Extracted ₹450.00 from blurred receipt.',
            'email_status': 'SIMULATED'
        },
        {
            'name': 'Rohan Mehta',
            'email': 'rohan@startuply.io',
            'phone': '+91 99887 76655',
            'company': 'Startuply Inc',
            'designation': 'Founder & CEO',
            'status': 'COMPLETED',
            'order_status': 'VERIFIED',
            'txn_id': '948201938572',
            'event': event2,
            'email_status': 'SENT'
        },
        {
            'name': 'Sneha Patel',
            'email': 'sneha.patel@designstudio.co',
            'phone': '+91 97654 32109',
            'company': 'Apex Design Studio',
            'designation': 'Principal UI Designer',
            'status': 'COMPLETED',
            'order_status': 'VERIFIED',
            'txn_id': '778899001122',
            'event': event4,
            'email_status': 'SENT'
        },
        {
            'name': 'Vikram Rathi',
            'email': 'vikram.rathi@devopsglobal.net',
            'phone': '+91 98450 12345',
            'company': 'DevOps Global Solutions',
            'designation': 'Cloud SRE Lead',
            'status': 'COMPLETED',
            'order_status': 'VERIFIED',
            'txn_id': '334455667788',
            'event': event3,
            'email_status': 'SENT'
        },
        {
            'name': 'Kavita Menon',
            'email': 'kavita.m@eduworld.in',
            'phone': '+91 94470 55443',
            'company': 'EduWorld Academy',
            'designation': 'Research Scholar',
            'status': 'PENDING',
            'order_status': 'PENDING',
            'txn_id': '',
            'event': event2,
            'email_status': 'SIMULATED'
        },
        {
            'name': 'Arjun Subramaniam',
            'email': 'arjun.subramaniam@cyberdefense.org',
            'phone': '+91 98840 99887',
            'company': 'CyberDefense Systems',
            'designation': 'Security Specialist',
            'status': 'COMPLETED',
            'order_status': 'VERIFIED',
            'txn_id': '556677889900',
            'event': event1,
            'email_status': 'SENT'
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

        pass_code = ''
        if item['status'] == 'COMPLETED':
            attendee, _ = Attendee.objects.get_or_create(registration=reg)
            pass_code = attendee.pass_code
            if item['txn_id']:
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
                        'review_notes': 'Auto-verified by AI OCR and instant verification rules.'
                    }
                )

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

        # Create EmailLog entry for preview in dashboard
        if not EmailLog.objects.filter(recipient_email=cust.email, subject__contains=reg.registration_code).exists():
            EmailLog.objects.create(
                tenant=ev.tenant,
                recipient_email=cust.email,
                event_type='REGISTRATION_COMPLETED' if item['status'] == 'COMPLETED' else 'REGISTRATION_CREATED',
                recipient_name=cust.name,
                subject=f"Official Pass: {ev.title} - {reg.registration_code}",
                status=item.get('email_status', 'SENT'),
                body_html=f"""
                <div style="font-family: sans-serif; padding: 20px; color: #1e293b; max-width: 600px; margin: auto;">
                    <h2 style="color: #1a73e8; margin-top:0;">{ev.title}</h2>
                    <p>Dear <strong>{cust.name}</strong>,</p>
                    <p>Your registration for <strong>{ev.title}</strong> has been successfully confirmed!</p>
                    <div style="background:#f8fafc; border:1px solid #e2e8f0; padding:15px; border-radius:8px; margin: 15px 0;">
                        <p style="margin:4px 0;"><strong>Registration Code:</strong> {reg.registration_code}</p>
                        <p style="margin:4px 0;"><strong>Pass Code:</strong> {pass_code or 'PASS-DEMO-001'}</p>
                        <p style="margin:4px 0;"><strong>Venue:</strong> {ev.venue}</p>
                        <p style="margin:4px 0;"><strong>Amount Paid:</strong> ₹{order.amount}</p>
                    </div>
                    <p style="color: #64748b; font-size: 13px;">Please present your digital pass QR code at the event entrance.</p>
                </div>
                """
            )

        log_audit_event('REGISTRATION_CREATED', reg.registration_code, {'customer': cust.email, 'event': ev.title}, tenant=ev.tenant)

    print("  [+] Successfully seeded 4 Events, 8 Registrations, Verified Orders, Attendee Passes & Email Logs")
    print("\n[SUCCESS] Platform Sample Data Ready!")

if __name__ == '__main__':
    seed()
