from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    LanguageViewSet,
    ProductCategoryViewSet,
    ProductTypeViewSet,
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
    login_client
)

router = DefaultRouter()
router.register(r'languages', LanguageViewSet, basename='language')
router.register(r'categories', ProductCategoryViewSet, basename='product-category')
router.register(r'types', ProductTypeViewSet, basename='product-type')
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
    path('', include(router.urls)),
    # Client authentication endpoints (public access)
    path('clients/register/', register_client, name='register-client'),
    path('clients/login/', login_client, name='login-client'),
]
