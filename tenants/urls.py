from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TenantViewSet, public_homepage, register_tenant, register_tenant_form

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)

urlpatterns = [
    path('', public_homepage, name='public_homepage'),
    path('register-tenant/', register_tenant_form, name='register_tenant_form'),
    path('api/register/', register_tenant, name='register_tenant'),
    path('api/', include(router.urls)),
]
