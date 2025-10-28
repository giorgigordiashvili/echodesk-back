from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TenantViewSet, public_homepage, register_tenant, register_tenant_with_payment,
    register_tenant_form, get_tenant_language, update_tenant_language, get_tenant_config,
    get_all_tenants, check_deployment_status, tenant_login, tenant_logout,
    tenant_dashboard, tenant_profile, update_tenant_profile, change_tenant_password
)
from .package_views import (
    PackageViewSet, list_packages_by_model, calculate_pricing, get_package_features,
    get_my_subscription
)
from .payment_views import (
    create_subscription_payment, check_payment_status, bog_webhook, cancel_subscription,
    get_saved_card_info, delete_saved_card, manual_payment
)
from .cron_views import (
    cron_recurring_payments, cron_subscription_check, cron_health_check
)
from .cors_test_views import cors_test, preflight_test
from .cors_views import simple_cors_test

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)
router.register(r'packages', PackageViewSet, basename='packages')

urlpatterns = [
    path('', public_homepage, name='public_homepage'),
    path('register-tenant/', register_tenant_form, name='register_tenant_form'),
    path('api/register/', register_tenant, name='register_tenant'),
    path('api/register-with-payment/', register_tenant_with_payment, name='register_tenant_with_payment'),
    
    # Package endpoints (public access for registration)
    path('api/packages/', include([
        path('by-model/', list_packages_by_model, name='list_packages_by_model'),
        path('calculate-pricing/', calculate_pricing, name='calculate_pricing'),
        path('<int:package_id>/features/', get_package_features, name='get_package_features'),
    ])),

    # Subscription endpoints (authenticated access)
    path('api/subscription/me/', get_my_subscription, name='get_my_subscription'),

    # Payment endpoints
    path('api/payments/create/', create_subscription_payment, name='create_subscription_payment'),
    path('api/payments/status/<str:payment_id>/', check_payment_status, name='check_payment_status'),
    path('api/payments/webhook/', bog_webhook, name='bog_webhook'),
    path('api/payments/cancel/', cancel_subscription, name='cancel_subscription'),
    path('api/payments/saved-card/', get_saved_card_info, name='get_saved_card_info'),
    path('api/payments/saved-card/delete/', delete_saved_card, name='delete_saved_card'),
    path('api/payments/manual/', manual_payment, name='manual_payment'),

    # Cron job endpoints (called by DigitalOcean Functions)
    path('api/cron/recurring-payments/', cron_recurring_payments, name='cron_recurring_payments'),
    path('api/cron/subscription-check/', cron_subscription_check, name='cron_subscription_check'),
    path('api/cron/health/', cron_health_check, name='cron_health_check'),

    # Authentication endpoints
    path('api/auth/login/', tenant_login, name='tenant_login'),
    path('api/auth/logout/', tenant_logout, name='tenant_logout'),
    path('api/auth/dashboard/', tenant_dashboard, name='tenant_dashboard'),
    path('api/auth/profile/', tenant_profile, name='tenant_profile'),
    path('api/auth/profile/update/', update_tenant_profile, name='update_tenant_profile'),
    path('api/auth/change-password/', change_tenant_password, name='change_tenant_password'),
    
    # Tenant configuration endpoints
    path('api/tenant/language/', get_tenant_language, name='get_tenant_language'),
    path('api/tenant/language/update/', update_tenant_language, name='update_tenant_language'),
    path('api/tenant/config/', get_tenant_config, name='get_tenant_config'),
    path('api/tenants/list/', get_all_tenants, name='get_all_tenants'),
    path('api/deployment-status/<int:tenant_id>/', check_deployment_status, name='check_deployment_status'),
    
    # CORS testing endpoints
    path('api/cors-test/', cors_test, name='cors_test'),
    path('api/cors-simple/', simple_cors_test, name='simple_cors_test'),
    path('api/preflight-test/', preflight_test, name='preflight_test'),
    
    # Admin API endpoints
    path('api/', include(router.urls)),
]
