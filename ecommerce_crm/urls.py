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
from .views_client import (
    ClientProductViewSet,
    ClientAddressViewSet as ClientClientAddressViewSet,
    ClientFavoriteViewSet,
    ClientCartViewSet,
    ClientCartItemViewSet,
    ClientOrderViewSet,
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

# Client router - requires client JWT authentication
client_router = DefaultRouter()
client_router.register(r'products', ClientProductViewSet, basename='client-product')
client_router.register(r'addresses', ClientClientAddressViewSet, basename='client-address')
client_router.register(r'favorites', ClientFavoriteViewSet, basename='client-favorite')
client_router.register(r'cart', ClientCartViewSet, basename='client-cart')
client_router.register(r'cart-items', ClientCartItemViewSet, basename='client-cart-item')
client_router.register(r'orders', ClientOrderViewSet, basename='client-order')

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
    # Client-facing endpoints (requires client JWT)
    path('client/', include(client_router.urls)),
    # Admin endpoints (requires admin JWT)
    path('admin/', include(admin_router.urls)),
]
