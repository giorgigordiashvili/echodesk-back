"""
URL Configuration for Invoice Management
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    InvoiceSettingsViewSet,
    InvoiceViewSet,
    InvoiceLineItemViewSet,
    InvoicePaymentViewSet,
    InvoiceTemplateViewSet,
    ClientViewSet,
    InvoiceMaterialViewSet
)

# Create a router and register our viewsets
router = DefaultRouter()
router.register(r'settings', InvoiceSettingsViewSet, basename='invoice-settings')
router.register(r'invoices', InvoiceViewSet, basename='invoices')
router.register(r'line-items', InvoiceLineItemViewSet, basename='invoice-line-items')
router.register(r'payments', InvoicePaymentViewSet, basename='invoice-payments')
router.register(r'templates', InvoiceTemplateViewSet, basename='invoice-templates')
router.register(r'clients', ClientViewSet, basename='invoice-clients')
router.register(r'materials', InvoiceMaterialViewSet, basename='invoice-materials')

# Wire up our API using automatic URL routing
app_name = 'invoices'
urlpatterns = [
    path('', include(router.urls)),
]
