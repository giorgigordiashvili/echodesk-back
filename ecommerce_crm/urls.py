from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ProductCategoryViewSet,
    ProductTypeViewSet,
    AttributeDefinitionViewSet,
    ProductViewSet,
    ProductImageViewSet,
    ProductVariantViewSet
)

router = DefaultRouter()
router.register(r'categories', ProductCategoryViewSet, basename='product-category')
router.register(r'types', ProductTypeViewSet, basename='product-type')
router.register(r'attributes', AttributeDefinitionViewSet, basename='attribute')
router.register(r'products', ProductViewSet, basename='product')
router.register(r'images', ProductImageViewSet, basename='product-image')
router.register(r'variants', ProductVariantViewSet, basename='product-variant')

app_name = 'ecommerce_crm'

urlpatterns = [
    path('', include(router.urls)),
]
