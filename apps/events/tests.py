from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from apps.tenants.models import Tenant, ApiKey
from apps.events.models import Event
from apps.forms_builder.models import Form, FormField
from apps.registrations.models import Customer, Registration, Attendee
from apps.payments.models import Order, Payment
from apps.verification.models import Verification, PaymentEvidence
from apps.verification.engine import VerificationEngine

class EMSEndToEndTestCase(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Test Tenant', slug='test-tenant')
        self.event = Event.objects.create(
            tenant=self.tenant,
            title='Test Tech Summit 2026',
            registration_fee=Decimal('500.00'),
            upi_id='dinesh.b@superyes',
            upi_name='Dinesh',
            status='OPEN'
        )
        self.form = Form.objects.create(event=self.event, title='Registration')
        self.form.create_default_fields()
        self.client = Client()

    def test_event_and_form_provisioning(self):
        """Test event code generation and default form fields creation"""
        self.assertTrue(self.event.event_code.startswith('EVT-'))
        self.assertEqual(self.event.slug, 'test-tech-summit-2026')
        self.assertGreaterEqual(self.form.fields.count(), 5)

    def test_registration_and_upi_intent_generation(self):
        """Test customer registration and dynamic UPI intent URL generation"""
        customer = Customer.objects.create(
            tenant=self.tenant,
            name='Test User',
            email='test@example.com'
        )
        reg = Registration.objects.create(
            event=self.event,
            customer=customer,
            amount=self.event.registration_fee
        )
        order = Order.objects.create(
            registration=reg,
            amount=self.event.registration_fee,
            currency='INR'
        )

        self.assertTrue(reg.registration_code.startswith('REG-'))
        self.assertTrue(order.order_code.startswith('ORD-'))
        self.assertIn('upi://pay?', order.upi_intent_url)
        self.assertIn('pa=dinesh.b%40superyes', order.upi_intent_url)
        self.assertIn('am=500.00', order.upi_intent_url)

    def test_auto_verification_success_flow(self):
        """Test happy path: OCR extracted amount matches expected fee -> AUTO_VERIFIED & COMPLETED"""
        customer = Customer.objects.create(tenant=self.tenant, name='Alice', email='alice@test.com')
        reg = Registration.objects.create(event=self.event, customer=customer, amount=Decimal('500.00'))
        order = Order.objects.create(registration=reg, amount=Decimal('500.00'))
        evidence = PaymentEvidence.objects.create(order=order)

        ocr_data = {
            'amount': 500.0,
            'transaction_id': '987654321012',
            'payee': 'Dinesh',
            'date': '2026-08-28',
            'time': '14:30'
        }

        verification = VerificationEngine.process_evidence(order, evidence, ocr_data)
        
        self.assertEqual(verification.decision, 'AUTO_VERIFIED')
        self.assertTrue(verification.is_amount_matched)
        self.assertFalse(verification.is_duplicate_txn)
        
        order.refresh_from_db()
        reg.refresh_from_db()
        self.assertEqual(order.status, 'VERIFIED')
        self.assertEqual(reg.status, 'COMPLETED')
        self.assertTrue(Attendee.objects.filter(registration=reg).exists())

    def test_duplicate_transaction_fraud_protection(self):
        """Test duplicate UTR protection: re-submitting same txn ID triggers MANUAL_REVIEW & duplicate alert"""
        customer1 = Customer.objects.create(tenant=self.tenant, name='Bob', email='bob@test.com')
        reg1 = Registration.objects.create(event=self.event, customer=customer1, amount=Decimal('500.00'))
        order1 = Order.objects.create(registration=reg1, amount=Decimal('500.00'))
        evidence1 = PaymentEvidence.objects.create(order=order1)

        # Order 1 gets verified with Txn ID 112233445566
        VerificationEngine.process_evidence(order1, evidence1, {
            'amount': 500.0,
            'transaction_id': '112233445566',
            'payee': 'Dinesh'
        })

        # Order 2 tries to upload the same Txn ID 112233445566
        customer2 = Customer.objects.create(tenant=self.tenant, name='Charlie', email='charlie@test.com')
        reg2 = Registration.objects.create(event=self.event, customer=customer2, amount=Decimal('500.00'))
        order2 = Order.objects.create(registration=reg2, amount=Decimal('500.00'))
        evidence2 = PaymentEvidence.objects.create(order=order2)

        verification2 = VerificationEngine.process_evidence(order2, evidence2, {
            'amount': 500.0,
            'transaction_id': '112233445566', # Reused UTR
            'payee': 'Dinesh'
        })

        self.assertEqual(verification2.decision, 'MANUAL_REVIEW')
        self.assertTrue(verification2.is_duplicate_txn)
        
        order2.refresh_from_db()
        self.assertEqual(order2.status, 'MANUAL_REVIEW')

    def test_partner_rest_api(self):
        """Test Partner API: POST /api/v1/registrations/ creates registration and returns checkout URL"""
        payload = {
            'event_code': self.event.event_code,
            'name': 'Partner Attendee',
            'email': 'partner@company.com',
            'phone': '+91 99999 88888',
            'company': 'Partner Co',
            'designation': 'VP Engineering'
        }
        res = self.client.post('/api/v1/registrations/', data=payload, content_type='application/json')
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('payment_url', data)
        self.assertIn('registration_id', data)
        self.assertEqual(data['amount'], 500.0)
