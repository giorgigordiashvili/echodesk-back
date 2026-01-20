from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TenantViewSet, public_homepage, register_tenant, register_tenant_with_payment,
    register_tenant_form, get_tenant_language, update_tenant_language, get_tenant_config,
    get_all_tenants, check_deployment_status, tenant_login, tenant_logout,
    tenant_dashboard, tenant_profile, update_tenant_profile, change_tenant_password,
    tenant_settings, upload_logo, remove_logo, forced_password_change, upload_image,
    get_subscription_me, resolve_ecommerce_domain,
    get_dashboard_appearance, update_dashboard_appearance, reset_dashboard_appearance
)
from .payment_views import (
    create_subscription_payment, check_payment_status, bog_webhook, cancel_subscription,
    get_saved_card, remove_saved_card, set_default_card, manual_payment, add_new_card, list_invoices,
    reactivate_subscription_payment, add_ecommerce_card
)
from .cron_views import (
    cron_recurring_payments, cron_subscription_check, cron_health_check,
    cron_process_trial_expirations, cron_payment_retries, cron_calculate_metrics,
    cron_email_sync
)
from .feature_views import (
    FeatureViewSet, PermissionViewSet, TenantFeatureViewSet,
    TenantPermissionViewSet, add_feature_to_subscription,
    remove_feature_from_subscription, update_agent_count,
    get_available_features
)
from .cors_views import simple_cors_test
from .deployment_views import (
    deploy_frontend, get_deployment_status as get_frontend_deployment_status,
    redeploy_frontend, delete_deployment, update_deployment_env
)
from .security_views import (
    list_security_logs, security_logs_stats, my_security_logs,
    list_ip_whitelist, create_ip_whitelist, manage_ip_whitelist,
    toggle_ip_whitelist, get_current_ip
)

router = DefaultRouter()
router.register(r'tenants', TenantViewSet)
router.register(r'features', FeatureViewSet, basename='features')
router.register(r'permissions', PermissionViewSet, basename='permissions')
router.register(r'tenant-features', TenantFeatureViewSet, basename='tenant-features')
router.register(r'tenant-permissions', TenantPermissionViewSet, basename='tenant-permissions')

urlpatterns = [
    path('', public_homepage, name='public_homepage'),
    path('register-tenant/', register_tenant_form, name='register_tenant_form'),
    path('api/register/', register_tenant, name='register_tenant'),
    path('api/register-with-payment/', register_tenant_with_payment, name='register_tenant_with_payment'),

    # Subscription endpoints (authenticated access)
    path('api/subscription/me/', get_subscription_me, name='get_subscription_me'),
    path('api/subscription/features/add/', add_feature_to_subscription, name='add_feature_to_subscription'),
    path('api/subscription/features/remove/', remove_feature_from_subscription, name='remove_feature_from_subscription'),
    path('api/subscription/features/available/', get_available_features, name='get_available_features'),
    path('api/subscription/agent-count/', update_agent_count, name='update_agent_count'),

    # Payment endpoints
    path('api/payments/create/', create_subscription_payment, name='create_subscription_payment'),
    path('api/payments/status/<str:payment_id>/', check_payment_status, name='check_payment_status'),
    path('api/payments/webhook/', bog_webhook, name='bog_webhook'),
    path('api/payments/cancel/', cancel_subscription, name='cancel_subscription'),
    path('api/payments/saved-card/', get_saved_card, name='get_saved_card'),
    path('api/payments/saved-card/', remove_saved_card, name='remove_saved_card'),
    path('api/payments/saved-card/set-default/', set_default_card, name='set_default_card'),
    path('api/payments/saved-card/add/', add_new_card, name='add_new_card'),
    path('api/payments/saved-card/add-ecommerce/', add_ecommerce_card, name='add_ecommerce_card'),
    path('api/payments/manual/', manual_payment, name='manual_payment'),
    path('api/payments/reactivate/', reactivate_subscription_payment, name='reactivate_subscription_payment'),
    path('api/payments/invoices/', list_invoices, name='list_invoices'),

    # Cron job endpoints (called by DigitalOcean Functions)
    path('api/cron/recurring-payments/', cron_recurring_payments, name='cron_recurring_payments'),
    path('api/cron/subscription-check/', cron_subscription_check, name='cron_subscription_check'),
    path('api/cron/process-trial-expirations/', cron_process_trial_expirations, name='cron_process_trial_expirations'),
    path('api/cron/payment-retries/', cron_payment_retries, name='cron_payment_retries'),
    path('api/cron/calculate-metrics/', cron_calculate_metrics, name='cron_calculate_metrics'),
    path('api/cron/email-sync/', cron_email_sync, name='cron_email_sync'),
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

    # Dashboard appearance settings endpoints
    path('api/dashboard-appearance/', get_dashboard_appearance, name='get_dashboard_appearance'),
    path('api/dashboard-appearance/update/', update_dashboard_appearance, name='update_dashboard_appearance'),
    path('api/dashboard-appearance/reset/', reset_dashboard_appearance, name='reset_dashboard_appearance'),

    # Security endpoints
    path('api/security/logs/', list_security_logs, name='list_security_logs'),
    path('api/security/logs/stats/', security_logs_stats, name='security_logs_stats'),
    path('api/security/logs/me/', my_security_logs, name='my_security_logs'),
    path('api/security/ip-whitelist/', list_ip_whitelist, name='list_ip_whitelist'),
    path('api/security/ip-whitelist/create/', create_ip_whitelist, name='create_ip_whitelist'),
    path('api/security/ip-whitelist/<int:pk>/', manage_ip_whitelist, name='manage_ip_whitelist'),
    path('api/security/ip-whitelist/toggle/', toggle_ip_whitelist, name='toggle_ip_whitelist'),
    path('api/security/current-ip/', get_current_ip, name='get_current_ip'),

    # Upload endpoints
    path('api/upload/image/', upload_image, name='upload_image'),

    # CORS testing endpoints
    path('api/cors-simple/', simple_cors_test, name='simple_cors_test'),

    # Frontend deployment endpoints (Vercel)
    path('api/deployment/<int:tenant_id>/deploy/', deploy_frontend, name='deploy_frontend'),
    path('api/deployment/<int:tenant_id>/status/', get_frontend_deployment_status, name='get_frontend_deployment_status'),
    path('api/deployment/<int:tenant_id>/redeploy/', redeploy_frontend, name='redeploy_frontend'),
    path('api/deployment/<int:tenant_id>/delete/', delete_deployment, name='delete_deployment'),
    path('api/deployment/<int:tenant_id>/env/', update_deployment_env, name='update_deployment_env'),

    # Admin API endpoints
    path('api/', include(router.urls)),

    # Public Ecommerce API - Multi-tenant frontend domain resolution
    path('api/public/resolve-domain/', resolve_ecommerce_domain, name='resolve_ecommerce_domain'),
]
