from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, tenant_homepage

router = DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    path('', tenant_homepage, name='tenant_homepage'),
    path('api/', include(router.urls)),
]
