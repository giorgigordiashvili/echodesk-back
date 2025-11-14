"""
Invoice Management API Views
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import FileResponse, HttpResponse
from django.db.models import Q, Sum
from datetime import datetime, timedelta

from .models import (
    InvoiceSettings,
    Invoice,
    InvoiceLineItem,
    InvoicePayment,
    InvoiceTemplate
)
from .serializers import (
    InvoiceSettingsSerializer,
    InvoiceListSerializer,
    InvoiceDetailSerializer,
    InvoiceCreateUpdateSerializer,
    InvoiceLineItemSerializer,
    InvoicePaymentSerializer,
    InvoiceTemplateSerializer,
    ClientSerializer,
    ListItemMaterialSerializer
)
from ecommerce_crm.models import EcommerceClient, Product
from tickets.models import ItemList, ListItem
from tenants.permissions import require_subscription_feature
from .permissions import CanManageInvoices


class InvoiceSettingsViewSet(viewsets.ModelViewSet):
    """
    API endpoint for invoice settings management
    """
    queryset = InvoiceSettings.objects.all()
    serializer_class = InvoiceSettingsSerializer
    permission_classes = [IsAuthenticated, CanManageInvoices]
    http_method_names = ['get', 'post', 'put', 'patch']

    def list(self, request, *args, **kwargs):
        """Get or create invoice settings (singleton)"""
        settings, created = InvoiceSettings.objects.get_or_create()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """Update settings (create not allowed, use update instead)"""
        settings, created = InvoiceSettings.objects.get_or_create()
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        """Update invoice settings"""
        settings, created = InvoiceSettings.objects.get_or_create()
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(settings, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='upload-logo')
    def upload_logo(self, request):
        """Upload company logo"""
        settings, created = InvoiceSettings.objects.get_or_create()

        if 'logo' not in request.FILES:
            return Response(
                {'error': 'No logo file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        settings.logo = request.FILES['logo']
        settings.save()

        serializer = self.get_serializer(settings)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='upload-badge')
    def upload_badge(self, request):
        """Upload company badge/seal"""
        settings, created = InvoiceSettings.objects.get_or_create()

        if 'badge' not in request.FILES:
            return Response(
                {'error': 'No badge file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        settings.badge = request.FILES['badge']
        settings.save()

        serializer = self.get_serializer(settings)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='upload-signature')
    def upload_signature(self, request):
        """Upload signature image"""
        settings, created = InvoiceSettings.objects.get_or_create()

        if 'signature' not in request.FILES:
            return Response(
                {'error': 'No signature file provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        settings.signature = request.FILES['signature']
        settings.save()

        serializer = self.get_serializer(settings)
        return Response(serializer.data)

    @action(detail=False, methods=['delete'], url_path='remove-logo')
    def remove_logo(self, request):
        """Remove company logo"""
        settings = InvoiceSettings.objects.first()
        if settings and settings.logo:
            settings.logo.delete()
            settings.save()

        return Response({'message': 'Logo removed successfully'})

    @action(detail=False, methods=['delete'], url_path='remove-badge')
    def remove_badge(self, request):
        """Remove company badge"""
        settings = InvoiceSettings.objects.first()
        if settings and settings.badge:
            settings.badge.delete()
            settings.save()

        return Response({'message': 'Badge removed successfully'})

    @action(detail=False, methods=['delete'], url_path='remove-signature')
    def remove_signature(self, request):
        """Remove signature"""
        settings = InvoiceSettings.objects.first()
        if settings and settings.signature:
            settings.signature.delete()
            settings.save()

        return Response({'message': 'Signature removed successfully'})

    @action(detail=False, methods=['get'], url_path='debug-subscription')
    def debug_subscription(self, request):
        """Debug endpoint to check subscription state"""
        from tenants.permissions import get_tenant_subscription, has_subscription_feature

        subscription = get_tenant_subscription(request)

        if not subscription:
            return Response({
                'error': 'No subscription found',
                'tenant': request.tenant.schema_name if hasattr(request, 'tenant') else 'no-tenant'
            })

        # Get selected features
        selected_features = list(subscription.selected_features.values('id', 'key', 'name'))

        # Test the actual permission function
        has_feature_result = has_subscription_feature(request, 'invoice_management')

        return Response({
            'tenant': request.tenant.schema_name,
            'subscription': {
                'id': subscription.id,
                'is_active': subscription.is_active,
                'subscription_type': subscription.subscription_type,
                'agent_count': subscription.agent_count,
                'monthly_cost': float(subscription.monthly_cost),
            },
            'selected_features': selected_features,
            'has_invoice_management_query': subscription.selected_features.filter(key='invoice_management').exists(),
            'has_invoice_management_function': has_feature_result,
        })

    @action(detail=False, methods=['get'], url_path='available-itemlists')
    def available_itemlists(self, request):
        """Get list of available item lists that can be used for clients"""
        from tickets.models import ItemList
        from tickets.serializers import ItemListMinimalSerializer

        item_lists = ItemList.objects.filter(is_active=True)
        serializer = ItemListMinimalSerializer(item_lists, many=True)
        return Response(serializer.data)


class InvoiceViewSet(viewsets.ModelViewSet):
    """
    API endpoint for invoice management
    """
    queryset = Invoice.objects.all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'client', 'currency']
    search_fields = ['invoice_number', 'client__first_name', 'client__last_name', 'client__email']
    ordering_fields = ['created_at', 'issue_date', 'due_date', 'total']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return InvoiceListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return InvoiceCreateUpdateSerializer
        return InvoiceDetailSerializer

    @require_subscription_feature('invoice_management')
    def list(self, request, *args, **kwargs):
        """List invoices with filters"""
        queryset = self.filter_queryset(self.get_queryset())

        # Additional filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(issue_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(issue_date__lte=date_to)

        # Check for overdue invoices
        overdue = request.query_params.get('overdue')
        if overdue == 'true':
            queryset = queryset.filter(
                due_date__lt=timezone.now().date(),
                status__in=['sent', 'viewed', 'partially_paid']
            )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @require_subscription_feature('invoice_management')
    def retrieve(self, request, *args, **kwargs):
        """Get invoice details"""
        return super().retrieve(request, *args, **kwargs)

    @require_subscription_feature('invoice_management')
    def create(self, request, *args, **kwargs):
        """Create new invoice"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Set created_by
        invoice = serializer.save(created_by=request.user)

        # Return detailed response
        detail_serializer = InvoiceDetailSerializer(invoice, context={'request': request})
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

    @require_subscription_feature('invoice_management')
    def update(self, request, *args, **kwargs):
        """Update invoice (only if draft)"""
        instance = self.get_object()

        if instance.status != 'draft':
            return Response(
                {'error': 'Only draft invoices can be edited'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().update(request, *args, **kwargs)

    @require_subscription_feature('invoice_management')
    def destroy(self, request, *args, **kwargs):
        """Delete invoice (only if draft)"""
        instance = self.get_object()

        if instance.status != 'draft':
            return Response(
                {'error': 'Only draft invoices can be deleted'},
                status=status.HTTP_400_BAD_REQUEST
            )

        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    @require_subscription_feature('invoice_management')
    def finalize(self, request, pk=None):
        """Finalize invoice and generate PDF"""
        invoice = self.get_object()

        if invoice.status != 'draft':
            return Response(
                {'error': 'Only draft invoices can be finalized'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # TODO: Generate PDF here
        # invoice.generate_pdf()

        invoice.status = 'sent'
        invoice.save()

        serializer = self.get_serializer(invoice)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    @require_subscription_feature('invoice_management')
    def send_email(self, request, pk=None):
        """Send invoice via email"""
        invoice = self.get_object()

        if invoice.status == 'draft':
            return Response(
                {'error': 'Finalize invoice before sending'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # TODO: Implement email sending
        # send_invoice_email.delay(invoice.id)

        invoice.sent_date = timezone.now()
        if invoice.status == 'draft':
            invoice.status = 'sent'
        invoice.save()

        return Response({'message': 'Invoice sent successfully'})

    @action(detail=True, methods=['get'])
    @require_subscription_feature('invoice_management')
    def pdf(self, request, pk=None):
        """Download invoice PDF"""
        invoice = self.get_object()

        # TODO: Implement PDF generation
        # if not invoice.pdf_file or regenerate:
        #     invoice.generate_pdf()

        # For now, return placeholder
        return Response(
            {'message': 'PDF generation not yet implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )

    @action(detail=True, methods=['get'])
    @require_subscription_feature('invoice_management')
    def excel(self, request, pk=None):
        """Export invoice to Excel"""
        invoice = self.get_object()

        # TODO: Implement Excel export
        return Response(
            {'message': 'Excel export not yet implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )

    @action(detail=True, methods=['post'])
    @require_subscription_feature('invoice_management')
    def mark_paid(self, request, pk=None):
        """Quick mark invoice as paid"""
        invoice = self.get_object()

        # Create payment record
        InvoicePayment.objects.create(
            invoice=invoice,
            amount=invoice.total - invoice.paid_amount,
            payment_method=request.data.get('payment_method', 'bank_transfer'),
            payment_date=timezone.now(),
            recorded_by=request.user,
            notes=request.data.get('notes', '')
        )

        invoice.mark_as_paid()

        serializer = self.get_serializer(invoice)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    @require_subscription_feature('invoice_management')
    def duplicate(self, request, pk=None):
        """Duplicate an existing invoice"""
        original = self.get_object()

        # Create new invoice with copied data
        new_invoice_data = {
            'client': original.client.id,
            'currency': original.currency,
            'discount_amount': original.discount_amount,
            'notes': original.notes,
            'terms_and_conditions': original.terms_and_conditions,
            'template': original.template.id if original.template else None,
            'issue_date': timezone.now().date(),
            'due_date': timezone.now().date() + timedelta(days=30),
        }

        # Copy line items
        line_items = []
        for item in original.line_items.all():
            line_items.append({
                'item_source': item.item_source,
                'product': item.product.id if item.product else None,
                'list_item': item.list_item.id if item.list_item else None,
                'description': item.description,
                'quantity': item.quantity,
                'unit': item.unit,
                'unit_price': item.unit_price,
                'tax_rate': item.tax_rate,
                'discount_percent': item.discount_percent,
                'position': item.position,
            })

        new_invoice_data['line_items'] = line_items

        serializer = InvoiceCreateUpdateSerializer(data=new_invoice_data)
        serializer.is_valid(raise_exception=True)
        new_invoice = serializer.save(created_by=request.user)

        detail_serializer = InvoiceDetailSerializer(new_invoice, context={'request': request})
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    @require_subscription_feature('invoice_management')
    def stats(self, request):
        """Get invoice statistics"""
        queryset = self.get_queryset()

        # Current month stats
        now = timezone.now()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        current_month = queryset.filter(created_at__gte=current_month_start)

        total_invoiced = current_month.aggregate(Sum('total'))['total__sum'] or 0
        total_paid = current_month.filter(status='paid').aggregate(Sum('total'))['total__sum'] or 0
        outstanding = queryset.exclude(status__in=['paid', 'cancelled']).aggregate(Sum('total'))['total__sum'] or 0
        overdue_count = queryset.filter(
            due_date__lt=now.date(),
            status__in=['sent', 'viewed', 'partially_paid']
        ).count()

        return Response({
            'current_month': {
                'total_invoiced': total_invoiced,
                'total_paid': total_paid,
                'count': current_month.count()
            },
            'outstanding_amount': outstanding,
            'overdue_count': overdue_count
        })


class InvoiceLineItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint for invoice line items
    """
    queryset = InvoiceLineItem.objects.all()
    serializer_class = InvoiceLineItemSerializer
    permission_classes = [IsAuthenticated]

    @require_subscription_feature('invoice_management')
    def list(self, request, *args, **kwargs):
        """List line items (filtered by invoice if provided)"""
        queryset = self.get_queryset()

        invoice_id = request.query_params.get('invoice_id')
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'], url_path='reorder')
    @require_subscription_feature('invoice_management')
    def reorder(self, request):
        """Reorder line items"""
        items = request.data.get('items', [])

        for item_data in items:
            item = InvoiceLineItem.objects.get(id=item_data['id'])
            item.position = item_data['position']
            item.save()

        return Response({'message': 'Line items reordered successfully'})


class InvoicePaymentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for invoice payments
    """
    queryset = InvoicePayment.objects.all()
    serializer_class = InvoicePaymentSerializer
    permission_classes = [IsAuthenticated]

    @require_subscription_feature('invoice_management')
    def list(self, request, *args, **kwargs):
        """List payments (filtered by invoice if provided)"""
        queryset = self.get_queryset()

        invoice_id = request.query_params.get('invoice_id')
        if invoice_id:
            queryset = queryset.filter(invoice_id=invoice_id)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @require_subscription_feature('invoice_management')
    def create(self, request, *args, **kwargs):
        """Record a payment"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(recorded_by=request.user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InvoiceTemplateViewSet(viewsets.ModelViewSet):
    """
    API endpoint for invoice templates
    """
    queryset = InvoiceTemplate.objects.filter(is_active=True)
    serializer_class = InvoiceTemplateSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['name', 'description']

    @require_subscription_feature('invoice_management')
    def list(self, request, *args, **kwargs):
        """List active templates"""
        return super().list(request, *args, **kwargs)

    @require_subscription_feature('invoice_management')
    def create(self, request, *args, **kwargs):
        """Create new template"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    @require_subscription_feature('invoice_management')
    def preview(self, request, pk=None):
        """Preview template with sample data"""
        template = self.get_object()

        # TODO: Implement template preview with sample data
        return Response(
            {'message': 'Template preview not yet implemented'},
            status=status.HTTP_501_NOT_IMPLEMENTED
        )


class ClientViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for client selection in invoices
    """
    queryset = EcommerceClient.objects.filter(is_active=True)
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['first_name', 'last_name', 'email', 'phone']

    @require_subscription_feature('invoice_management')
    def list(self, request, *args, **kwargs):
        """List active clients"""
        return super().list(request, *args, **kwargs)


class InvoiceMaterialViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for materials (from ItemList) selection
    """
    queryset = ListItem.objects.filter(is_active=True)
    serializer_class = ListItemMaterialSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = ['label', 'custom_data']

    @require_subscription_feature('invoice_management')
    def list(self, request, *args, **kwargs):
        """List materials from invoice materials ItemList"""
        # Filter by invoice materials list
        list_title = request.query_params.get('list_title', 'Invoice Materials')

        try:
            item_list = ItemList.objects.get(title=list_title, is_active=True)
            queryset = self.get_queryset().filter(item_list=item_list)
        except ItemList.DoesNotExist:
            queryset = self.get_queryset().none()

        # Apply search
        queryset = self.filter_queryset(queryset)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
