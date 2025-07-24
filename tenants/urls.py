from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantViewSet, public_homepage

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)

urlpatterns = [
    path('', public_homepage, name='public_homepage'),
    path('api/', include(router.urls)),
]
