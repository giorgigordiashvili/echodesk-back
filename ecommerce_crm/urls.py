from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductCategoryViewSet,
    ProductTypeViewSet,
    AttributeDefinitionViewSet,
    ProductViewSet,
    ProductImageViewSet,
    ProductVariantViewSet,
    EcommerceClientViewSet,
    register_client,
    login_client
)

router = DefaultRouter()
router.register(r'categories', ProductCategoryViewSet, basename='product-category')
router.register(r'types', ProductTypeViewSet, basename='product-type')
router.register(r'attributes', AttributeDefinitionViewSet, basename='attribute')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'images', ProductImageViewSet, basename='product-image')
router.register(r'variants', ProductVariantViewSet, basename='product-variant')
router.register(r'clients', EcommerceClientViewSet, basename='ecommerce-client')

app_name = 'ecommerce_crm'

urlpatterns = [
    path('', include(router.urls)),
    # Client authentication endpoints (public access)
    path('clients/register/', register_client, name='register-client'),
    path('clients/login/', login_client, name='login-client'),
]
