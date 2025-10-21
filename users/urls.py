from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, GroupViewSet, PermissionViewSet, DepartmentViewSet, TenantGroupViewSet, NotificationViewSet, tenant_homepage

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'groups', GroupViewSet)
router.register(r'tenant-groups', TenantGroupViewSet)
router.register(r'permissions', PermissionViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('', tenant_homepage, name='tenant_homepage'),
    path('api/', include(router.urls)),
]
