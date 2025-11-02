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
    register_client,
    login_client,
    verify_email,
    request_password_reset,
    confirm_password_reset,
    get_current_client,
    ecommerce_payment_webhook
)

router = DefaultRouter()
router.register(r'languages', LanguageViewSet, basename='language')
router.register(r'attributes', AttributeDefinitionViewSet, basename='attribute')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'images', ProductImageViewSet, basename='product-image')
router.register(r'variants', ProductVariantViewSet, basename='product-variant')
router.register(r'clients', EcommerceClientViewSet, basename='ecommerce-client')
router.register(r'addresses', ClientAddressViewSet, basename='client-address')
router.register(r'favorites', FavoriteProductViewSet, basename='favorite-product')
router.register(r'cart', CartViewSet, basename='cart')
router.register(r'cart-items', CartItemViewSet, basename='cart-item')
router.register(r'orders', OrderViewSet, basename='order')

app_name = 'ecommerce_crm'

urlpatterns = [
    # Client authentication endpoints (public access) - MUST come before router
    # to prevent router from treating them as detail lookups
    path('clients/register/', register_client, name='register-client'),
    path('clients/login/', login_client, name='login-client'),
    path('clients/verify/', verify_email, name='verify-email'),
    path('clients/me/', get_current_client, name='current-client'),
    path('clients/password-reset/request/', request_password_reset, name='password-reset-request'),
    path('clients/password-reset/confirm/', confirm_password_reset, name='password-reset-confirm'),
    # Payment webhook (public access - called by BOG)
    path('payment-webhook/', ecommerce_payment_webhook, name='payment-webhook'),
    # Router URLs (should come last)
    path('', include(router.urls)),
]
