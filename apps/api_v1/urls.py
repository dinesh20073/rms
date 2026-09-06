from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EventViewSet, RegistrationViewSet, OrderStatusAPIView, 
    PaymentProofUploadAPIView, RevenueReportAPIView
)

router = DefaultRouter()
router.register(r'events', EventViewSet, basename='api-events')

urlpatterns = [
    path('', include(router.urls)),
    path('registrations/', RegistrationViewSet.as_view({'post': 'create'}), name='api-registration-create'),
    path('registrations/<str:registration_code>/', RegistrationViewSet.as_view({'get': 'retrieve'}), name='api-registration-detail'),
    path('orders/<str:order_code>/status/', OrderStatusAPIView.as_view(), name='api-order-status'),
    path('orders/<str:order_code>/payment-proof/', PaymentProofUploadAPIView.as_view(), name='api-payment-proof-upload'),
    path('reports/revenue/', RevenueReportAPIView.as_view(), name='api-revenue-report'),
]
