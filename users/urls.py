from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, TenantGroupViewSet, tenant_homepage

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'groups', TenantGroupViewSet)

urlpatterns = [
    path('', tenant_homepage, name='tenant_homepage'),
    path('api/', include(router.urls)),
]
