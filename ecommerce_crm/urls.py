from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LanguageViewSet,
    AttributeDefinitionViewSet,
    ProductViewSet,
    ProductImageViewSet,
    ProductVariantViewSet,
    EcommerceClientViewSet,
    ClientAddressViewSet,
    FavoriteProductViewSet,
    CartViewSet,
    CartItemViewSet,
    OrderViewSet,
    EcommerceSettingsViewSet,
    HomepageSectionViewSet,
    ShippingMethodViewSet,
    PromoCodeViewSet,
    ProductReviewAdminViewSet,
    register_client,
    login_client,
    logout_client,
    refresh_client_token,
    verify_email,
    resend_verification_code,
    request_password_reset,
    confirm_password_reset,
    get_current_client,
    ecommerce_payment_webhook,
    tbc_payment_webhook,
    flitt_payment_webhook,
    quickshipper_test_connection,
    quickshipper_quote,
    quickshipper_quote_guest,
    quickshipper_webhook,
)
from .views_client import (
    ClientProfileViewSet,
    ClientAttributeViewSet,
    ClientProductViewSet,
    ClientAddressViewSet as ClientClientAddressViewSet,
    ClientFavoriteViewSet,
    ClientCartViewSet,
    ClientCartItemViewSet,
    ClientOrderViewSet,
    ClientItemListViewSet,
    ClientLanguageViewSet,
    ClientShippingMethodViewSet,
    ClientProductReviewViewSet,
    add_client_card,
    list_client_cards,
    delete_client_card,
    set_default_client_card,
    get_homepage_config,
    get_store_theme,
    validate_promo_code,
    guest_checkout,
    get_order_by_public_token,
    change_password,
)

# Admin router - requires admin JWT authentication
admin_router = DefaultRouter()
admin_router.register(r'languages', LanguageViewSet, basename='language')
admin_router.register(r'attributes', AttributeDefinitionViewSet, basename='attribute')
admin_router.register(r'products', ProductViewSet, basename='product')
admin_router.register(r'images', ProductImageViewSet, basename='product-image')
admin_router.register(r'variants', ProductVariantViewSet, basename='product-variant')
admin_router.register(r'clients', EcommerceClientViewSet, basename='ecommerce-client')
admin_router.register(r'addresses', ClientAddressViewSet, basename='client-address')
admin_router.register(r'favorites', FavoriteProductViewSet, basename='favorite-product')
admin_router.register(r'cart', CartViewSet, basename='cart')
admin_router.register(r'cart-items', CartItemViewSet, basename='cart-item')
admin_router.register(r'orders', OrderViewSet, basename='order')
admin_router.register(r'settings', EcommerceSettingsViewSet, basename='ecommerce-settings')
admin_router.register(r'homepage-sections', HomepageSectionViewSet, basename='homepage-section')
admin_router.register(r'shipping-methods', ShippingMethodViewSet, basename='shipping-method')
admin_router.register(r'promo-codes', PromoCodeViewSet, basename='promo-code')
admin_router.register(r'reviews', ProductReviewAdminViewSet, basename='product-review-admin')

# Client router - public and authenticated client access
client_router = DefaultRouter()
client_router.register(r'profile', ClientProfileViewSet, basename='client-profile')
client_router.register(r'attributes', ClientAttributeViewSet, basename='client-attribute')
client_router.register(r'products', ClientProductViewSet, basename='client-product')
client_router.register(r'addresses', ClientClientAddressViewSet, basename='client-address')
client_router.register(r'favorites', ClientFavoriteViewSet, basename='client-favorite')
client_router.register(r'cart', ClientCartViewSet, basename='client-cart')
client_router.register(r'cart-items', ClientCartItemViewSet, basename='client-cart-item')
client_router.register(r'orders', ClientOrderViewSet, basename='client-order')
client_router.register(r'item-lists', ClientItemListViewSet, basename='client-item-list')
client_router.register(r'languages', ClientLanguageViewSet, basename='client-language')
client_router.register(r'shipping-methods', ClientShippingMethodViewSet, basename='client-shipping-method')

app_name = 'ecommerce_crm'

urlpatterns = [
    # Client authentication endpoints (public access) - MUST come before router
    # to prevent router from treating them as detail lookups
    path('clients/register/', register_client, name='register-client'),
    path('clients/login/', login_client, name='login-client'),
    path('clients/logout/', logout_client, name='logout-client'),
    path('clients/refresh-token/', refresh_client_token, name='refresh-client-token'),
    path('clients/verify/', verify_email, name='verify-email'),
    path('clients/resend-code/', resend_verification_code, name='resend-verification-code'),
    path('clients/me/', get_current_client, name='current-client'),
    path('clients/password-reset/request/', request_password_reset, name='password-reset-request'),
    path('clients/password-reset/confirm/', confirm_password_reset, name='password-reset-confirm'),
    path('clients/change-password/', change_password, name='change-password'),
    # Payment webhooks (public access - called by payment providers)
    path('payment-webhook/', ecommerce_payment_webhook, name='payment-webhook'),
    path('payment-webhook/tbc/', tbc_payment_webhook, name='tbc-payment-webhook'),
    path('payment-webhook/flitt/', flitt_payment_webhook, name='flitt-payment-webhook'),
    # Quickshipper courier integration
    path('admin/quickshipper/test-connection/', quickshipper_test_connection, name='quickshipper-test-connection'),
    path('client/shipping/quote/', quickshipper_quote, name='quickshipper-quote'),
    path('client/shipping/quote-guest/', quickshipper_quote_guest, name='quickshipper-quote-guest'),
    path('shipping-webhook/quickshipper/', quickshipper_webhook, name='quickshipper-webhook'),
    # Client-facing card management endpoints (requires client JWT)
    path('client/cards/add/', add_client_card, name='client-add-card'),
    path('client/cards/', list_client_cards, name='client-list-cards'),
    path('client/cards/<int:card_id>/delete/', delete_client_card, name='client-delete-card'),
    path('client/cards/<int:card_id>/set-default/', set_default_client_card, name='client-set-default-card'),
    # Public homepage endpoint
    path('client/homepage/', get_homepage_config, name='client-homepage'),
    # Public theme endpoint
    path('client/theme/', get_store_theme, name='client-theme'),
    # Promo code validation
    path('client/promo/validate/', validate_promo_code, name='client-promo-validate'),
    # Guest checkout (public access)
    path('client/guest-checkout/', guest_checkout, name='client-guest-checkout'),
    # Public order lookup by URL-safe token (guest order tracking)
    path('client/orders/by-token/', get_order_by_public_token, name='client-order-by-token'),
    # Product reviews (nested under products)
    path('client/products/<int:product_pk>/reviews/',
         ClientProductReviewViewSet.as_view({'get': 'list', 'post': 'create'}),
         name='client-product-reviews'),
    # Client-facing endpoints (requires client JWT)
    path('client/', include(client_router.urls)),
    # Admin endpoints (requires admin JWT)
    path('admin/', include(admin_router.urls)),
]
