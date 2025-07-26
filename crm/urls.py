from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CallLogViewSet, ClientViewSet, SipConfigurationViewSet, sip_webhook, recording_webhook

router = DefaultRouter()
router.register(r'call-logs', CallLogViewSet, basename='call-logs')
router.register(r'clients', ClientViewSet, basename='clients')
router.register(r'sip-configurations', SipConfigurationViewSet, basename='sip-configurations')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/webhooks/sip/', sip_webhook, name='sip-webhook'),
    path('api/webhooks/recording/', recording_webhook, name='recording-webhook'),
]
