"""
Public schema URL configuration.
This handles routes for the public schema (tenant management).
"""
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from social_integrations import legal_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # Legal pages (required for Facebook app compliance)
    path('legal/privacy-policy/', legal_views.privacy_policy, name='privacy-policy'),
    path('legal/terms-of-service/', legal_views.terms_of_service, name='terms-of-service'),
    path('legal/data-deletion/', legal_views.user_data_deletion, name='data-deletion'),
    path('legal/data-deletion-status/', legal_views.data_deletion_status, name='data-deletion-status'),
    path('legal/deauthorize/', legal_views.deauthorize_callback, name='deauthorize-callback'),
    
    # Social integrations (needed for OAuth callbacks)
    path('api/social/', include('social_integrations.urls')),
    
    # Public/tenant management endpoints
    path('', include('tenants.urls')),
]
