from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TenantViewSet, public_homepage, register_tenant, register_tenant_form, 
    get_tenant_language, update_tenant_language, get_tenant_config,
    get_all_tenants, check_deployment_status
)
from .cors_test_views import cors_test, preflight_test
from .cors_views import simple_cors_test

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)

urlpatterns = [
    path('', public_homepage, name='public_homepage'),
    path('register-tenant/', register_tenant_form, name='register_tenant_form'),
    path('api/register/', register_tenant, name='register_tenant'),
    path('api/tenant/language/', get_tenant_language, name='get_tenant_language'),
    path('api/tenant/language/update/', update_tenant_language, name='update_tenant_language'),
    path('api/tenant/config/', get_tenant_config, name='get_tenant_config'),
    path('api/tenants/list/', get_all_tenants, name='get_all_tenants'),
    path('api/deployment-status/<int:tenant_id>/', check_deployment_status, name='check_deployment_status'),
    path('api/cors-test/', cors_test, name='cors_test'),
    path('api/cors-simple/', simple_cors_test, name='simple_cors_test'),
    path('api/preflight-test/', preflight_test, name='preflight_test'),
    path('api/', include(router.urls)),
]
