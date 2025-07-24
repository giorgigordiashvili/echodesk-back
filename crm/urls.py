from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CallLogViewSet, ClientViewSet

router = DefaultRouter()
router.register(r'call-logs', CallLogViewSet)
router.register(r'clients', ClientViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
]
