from rest_framework import serializers
from apps.events.models import Event
from apps.registrations.models import Registration, Customer, Attendee
from apps.payments.models import Order, Payment
from apps.verification.models import Verification, PaymentEvidence

class EventSerializer(serializers.ModelSerializer):
    is_registration_open = serializers.BooleanField(read_only=True)
    registration_url = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            'id', 'event_code', 'title', 'slug', 'description', 
            'registration_fee', 'currency', 'upi_id', 'upi_name',
            'venue', 'status', 'is_registration_open', 'registration_url',
            'created_at'
        ]

    def get_registration_url(self, obj):
        request = self.context.get('request')
        url = f"/register/{obj.slug}/"
        return request.build_absolute_uri(url) if request else url

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'name', 'email', 'phone', 'company', 'designation']

class AttendeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendee
        fields = ['pass_code', 'is_checked_in', 'checked_in_at']

class OrderSerializer(serializers.ModelSerializer):
    gpay_intent = serializers.CharField(read_only=True)
    phonepe_intent = serializers.CharField(read_only=True)
    payment_url = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['order_code', 'amount', 'currency', 'status', 'upi_intent_url', 'gpay_intent', 'phonepe_intent', 'payment_url', 'created_at']

    def get_payment_url(self, obj):
        request = self.context.get('request')
        url = f"/pay/{obj.order_code}/"
        return request.build_absolute_uri(url) if request else url

class RegistrationSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    order = OrderSerializer(read_only=True)
    attendee = AttendeeSerializer(source='attendee_pass', read_only=True)
    status_url = serializers.SerializerMethodField()

    class Meta:
        model = Registration
        fields = [
            'registration_code', 'event', 'customer', 'status', 
            'amount', 'form_responses', 'order', 'attendee', 'status_url', 'created_at'
        ]

    def get_status_url(self, obj):
        request = self.context.get('request')
        url = f"/status/{obj.registration_code}/"
        return request.build_absolute_uri(url) if request else url

class PartnerRegistrationCreateSerializer(serializers.Serializer):
    event_code = serializers.CharField(required=True)
    name = serializers.CharField(required=True)
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(required=False, default='')
    company = serializers.CharField(required=False, default='')
    designation = serializers.CharField(required=False, default='')
    custom_responses = serializers.DictField(required=False, default=dict)
