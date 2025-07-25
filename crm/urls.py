from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CallLogViewSet, ClientViewSet, SipConfigurationViewSet

router = DefaultRouter()
router.register(r'call-logs', CallLogViewSet, basename='call-logs')
router.register(r'clients', ClientViewSet, basename='clients')
router.register(r'sip-configurations', SipConfigurationViewSet, basename='sip-configurations')

urlpatterns = [
    path('api/', include(router.urls)),
]
