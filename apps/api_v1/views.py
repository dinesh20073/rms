from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count
from django.utils import timezone
from apps.events.models import Event
from apps.registrations.models import Registration, Customer
from apps.payments.models import Order
from apps.verification.models import PaymentEvidence, Verification
from apps.verification.ocr_service import OCRExtractor
from apps.verification.engine import VerificationEngine
from apps.audit.services import log_audit_event
from .serializers import (
    EventSerializer, RegistrationSerializer, OrderSerializer, 
    PartnerRegistrationCreateSerializer
)

class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    lookup_field = 'event_code'

class RegistrationViewSet(viewsets.ViewSet):
    lookup_field = 'registration_code'

    def retrieve(self, request, registration_code=None):
        registration = get_object_or_404(Registration, registration_code=registration_code)
        serializer = RegistrationSerializer(registration, context={'request': request})
        return Response(serializer.data)

    def create(self, request):
        serializer = PartnerRegistrationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        event = get_object_or_404(Event, event_code=data['event_code'])
        tenant = event.tenant

        customer, _ = Customer.objects.get_or_create(
            tenant=tenant,
            email=data['email'].lower(),
            defaults={
                'name': data['name'],
                'phone': data.get('phone', ''),
                'company': data.get('company', ''),
                'designation': data.get('designation', '')
            }
        )

        registration = Registration.objects.create(
            event=event,
            customer=customer,
            amount=event.registration_fee,
            form_responses=data.get('custom_responses', {}),
            status='PENDING'
        )

        order = Order.objects.create(
            registration=registration,
            amount=event.registration_fee,
            currency=event.currency,
            status='PENDING'
        )

        log_audit_event(
            'PARTNER_API_CALL', 
            registration.registration_code, 
            {'source': 'REST_API', 'event': event.event_code, 'customer': customer.email}, 
            tenant=tenant,
            actor='Partner API'
        )

        payment_url = request.build_absolute_uri(f"/pay/{order.order_code}/")
        return Response({
            "status": "success",
            "registration_id": registration.registration_code,
            "order_id": order.order_code,
            "amount": float(order.amount),
            "currency": order.currency,
            "payment_url": payment_url,
            "status_url": request.build_absolute_uri(f"/status/{registration.registration_code}/")
        }, status=status.HTTP_201_CREATED)

class OrderStatusAPIView(APIView):
    def get(self, request, order_code):
        order = get_object_or_404(Order, order_code=order_code)
        reg = order.registration
        verification = getattr(order, 'verification', None)

        return Response({
            "order_code": order.order_code,
            "registration_code": reg.registration_code,
            "event": reg.event.title,
            "amount": float(order.amount),
            "currency": order.currency,
            "payment_status": order.status,
            "registration_status": reg.status,
            "verification_decision": verification.decision if verification else "PENDING",
            "is_completed": reg.status == 'COMPLETED'
        })

class PaymentProofUploadAPIView(APIView):
    def post(self, request, order_code):
        order = get_object_or_404(Order, order_code=order_code)
        screenshot = request.FILES.get('screenshot')
        
        # Optional override for mock testing from API
        mock_amount = request.data.get('mock_amount')
        mock_txn_id = request.data.get('mock_transaction_id')

        if not screenshot and not mock_txn_id:
            return Response({"error": "Screenshot file or mock parameters required"}, status=status.HTTP_400_BAD_REQUEST)

        evidence = PaymentEvidence.objects.create(
            order=order,
            screenshot=screenshot if screenshot else 'payment_proofs/sample.png'
        )

        if screenshot:
            ocr_data = OCRExtractor.extract_from_image(evidence.screenshot)
        else:
            ocr_data = {
                'amount': float(mock_amount) if mock_amount else float(order.amount),
                'transaction_id': mock_txn_id,
                'payee': order.registration.event.upi_name,
                'date': timezone.now().strftime('%Y-%m-%d'),
                'time': timezone.now().strftime('%H:%M')
            }

        verification = VerificationEngine.process_evidence(order, evidence, ocr_data)

        from apps.notifications.services import send_order_created_email
        send_order_created_email(order.registration)

        return Response({
            "status": "processed",
            "decision": verification.decision,
            "order_status": order.status,
            "registration_status": order.registration.status,
            "extracted_data": ocr_data,
            "notes": verification.review_notes
        })

class RevenueReportAPIView(APIView):
    def get(self, request):
        total_revenue = Order.objects.filter(status='VERIFIED').aggregate(total=Sum('amount'))['total'] or 0
        total_orders = Order.objects.count()
        verified_orders = Order.objects.filter(status='VERIFIED').count()
        pending_review = Order.objects.filter(status='MANUAL_REVIEW').count()

        return Response({
            "total_revenue": float(total_revenue),
            "currency": "INR",
            "total_orders": total_orders,
            "verified_orders": verified_orders,
            "pending_review": pending_review
        })

class HealthCheckAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        from django.db import connection
        from django.contrib.auth.models import User
        db_connected = False
        vendor = connection.vendor
        error = None
        user_count = 0
        event_count = 0

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
            db_connected = True
            user_count = User.objects.count()
            event_count = Event.objects.count()
        except Exception as e:
            error = str(e)

        return Response({
            "status": "online" if db_connected else "error",
            "database": {
                "connected": db_connected,
                "vendor": vendor,
                "is_supabase_postgres": vendor == "postgresql",
                "users_count": user_count,
                "events_count": event_count,
                "error": error
            }
        })

