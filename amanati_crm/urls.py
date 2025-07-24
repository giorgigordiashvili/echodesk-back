"""
URL configuration for amanati_crm project.
This is the main URL configuration for tenant-specific routes.
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # Tenant-specific apps
    path('', include('users.urls')),
    path('', include('crm.urls')),
    path('', include('tickets.urls')),
]
