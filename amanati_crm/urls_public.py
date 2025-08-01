"""
Public schema URL configuration.
This handles routes for the public schema (tenant management).
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # Social integrations (needed for OAuth callbacks)
    path('api/social/', include('social_integrations.urls')),
    
    # Public/tenant management endpoints
    path('', include('tenants.urls')),
]
