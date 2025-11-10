from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TenantViewSet, public_homepage, register_tenant, register_tenant_with_payment,
    register_tenant_form, get_tenant_language, update_tenant_language, get_tenant_config,
    get_all_tenants, check_deployment_status, tenant_login, tenant_logout,
    tenant_dashboard, tenant_profile, update_tenant_profile, change_tenant_password,
    tenant_settings, upload_logo, remove_logo, forced_password_change, upload_image
)
from .package_views import (
    PackageViewSet, list_packages_by_model, calculate_pricing, get_package_features,
    get_my_subscription, calculate_custom_package_price, list_available_features
)
from .payment_views import (
    create_subscription_payment, check_payment_status, bog_webhook, cancel_subscription,
    get_saved_card, remove_saved_card, set_default_card, manual_payment, add_new_card, list_invoices
)
from .upgrade_views import (
    upgrade_preview, upgrade_immediate, upgrade_scheduled, cancel_scheduled_upgrade
)
from .cron_views import (
    cron_recurring_payments, cron_subscription_check, cron_health_check,
    cron_process_trial_expirations
)
from .feature_views import (
    FeatureViewSet, PermissionViewSet, TenantFeatureViewSet,
    TenantPermissionViewSet
)
from .cors_views import simple_cors_test

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)
router.register(r'packages', PackageViewSet, basename='packages')
router.register(r'features', FeatureViewSet, basename='features')
router.register(r'permissions', PermissionViewSet, basename='permissions')
router.register(r'tenant-features', TenantFeatureViewSet, basename='tenant-features')
router.register(r'tenant-permissions', TenantPermissionViewSet, basename='tenant-permissions')

urlpatterns = [
    path('', public_homepage, name='public_homepage'),
    path('register-tenant/', register_tenant_form, name='register_tenant_form'),
    path('api/register/', register_tenant, name='register_tenant'),
    path('api/register-with-payment/', register_tenant_with_payment, name='register_tenant_with_payment'),
    
    # Package endpoints (public access for registration)
    path('api/packages/', include([
        path('by-model/', list_packages_by_model, name='list_packages_by_model'),
        path('calculate-pricing/', calculate_pricing, name='calculate_pricing'),
        path('calculate-custom-price/', calculate_custom_package_price, name='calculate_custom_package_price'),
        path('available-features/', list_available_features, name='list_available_features'),
        path('<int:package_id>/features/', get_package_features, name='get_package_features'),
    ])),

    # Subscription endpoints (authenticated access)
    path('api/subscription/me/', get_my_subscription, name='get_my_subscription'),

    # Payment endpoints
    path('api/payments/create/', create_subscription_payment, name='create_subscription_payment'),
    path('api/payments/status/<str:payment_id>/', check_payment_status, name='check_payment_status'),
    path('api/payments/webhook/', bog_webhook, name='bog_webhook'),
    path('api/payments/cancel/', cancel_subscription, name='cancel_subscription'),
    path('api/payments/saved-card/', get_saved_card, name='get_saved_card'),
    path('api/payments/saved-card/', remove_saved_card, name='remove_saved_card'),
    path('api/payments/saved-card/set-default/', set_default_card, name='set_default_card'),
    path('api/payments/saved-card/add/', add_new_card, name='add_new_card'),
    path('api/payments/manual/', manual_payment, name='manual_payment'),
    path('api/payments/invoices/', list_invoices, name='list_invoices'),

    # Package upgrade endpoints (authenticated access)
    path('api/upgrade/preview/', upgrade_preview, name='upgrade_preview'),
    path('api/upgrade/immediate/', upgrade_immediate, name='upgrade_immediate'),
    path('api/upgrade/scheduled/', upgrade_scheduled, name='upgrade_scheduled'),
    path('api/upgrade/cancel-scheduled/', cancel_scheduled_upgrade, name='cancel_scheduled_upgrade'),

    # Cron job endpoints (called by DigitalOcean Functions)
    path('api/cron/recurring-payments/', cron_recurring_payments, name='cron_recurring_payments'),
    path('api/cron/subscription-check/', cron_subscription_check, name='cron_subscription_check'),
    path('api/cron/process-trial-expirations/', cron_process_trial_expirations, name='cron_process_trial_expirations'),
    path('api/cron/health/', cron_health_check, name='cron_health_check'),

    # Authentication endpoints
    path('api/auth/login/', tenant_login, name='tenant_login'),
    path('api/auth/logout/', tenant_logout, name='tenant_logout'),
    path('api/auth/dashboard/', tenant_dashboard, name='tenant_dashboard'),
    path('api/auth/profile/', tenant_profile, name='tenant_profile'),
    path('api/auth/profile/update/', update_tenant_profile, name='update_tenant_profile'),
    path('api/auth/change-password/', change_tenant_password, name='change_tenant_password'),
    path('api/auth/forced-password-change/', forced_password_change, name='forced_password_change'),
    
    # Tenant configuration endpoints
    path('api/tenant/language/', get_tenant_language, name='get_tenant_language'),
    path('api/tenant/language/update/', update_tenant_language, name='update_tenant_language'),
    path('api/tenant/config/', get_tenant_config, name='get_tenant_config'),
    path('api/tenants/list/', get_all_tenants, name='get_all_tenants'),
    path('api/deployment-status/<int:tenant_id>/', check_deployment_status, name='check_deployment_status'),

    # Tenant settings endpoints
    path('api/tenant-settings/', tenant_settings, name='tenant_settings'),
    path('api/tenant-settings/upload-logo/', upload_logo, name='upload_logo'),
    path('api/tenant-settings/remove-logo/', remove_logo, name='remove_logo'),

    # Upload endpoints
    path('api/upload/image/', upload_image, name='upload_image'),

    # CORS testing endpoints
    path('api/cors-simple/', simple_cors_test, name='simple_cors_test'),
    
    # Admin API endpoints
    path('api/', include(router.urls)),
]
