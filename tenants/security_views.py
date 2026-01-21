"""
Security API Views for login/logout logs and IP whitelist management.
"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from tenant_schemas.utils import get_public_schema_name
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes

from .models import SecurityLog, TenantIPWhitelist, Tenant
from .serializers import SecurityLogSerializer, TenantIPWhitelistSerializer
from .security_service import SecurityService

import logging

logger = logging.getLogger(__name__)


class SecurityLogPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200


class IsSuperUser(permissions.BasePermission):
    """Only allow superusers to access"""
    def has_permission(self, request, view):
        return request.user and request.user.is_superuser


# ============================================================
# Security Logs Endpoints
# ============================================================

@extend_schema(
    operation_id='list_security_logs',
    summary='List Security Logs',
    description='Get paginated list of security logs with filtering options. Superadmin only.',
    parameters=[
        OpenApiParameter('event_type', OpenApiTypes.STR, description='Filter by event type (login_success, login_failed, logout, token_expired)'),
        OpenApiParameter('user_id', OpenApiTypes.INT, description='Filter by user ID'),
        OpenApiParameter('ip_address', OpenApiTypes.STR, description='Filter by IP address'),
        OpenApiParameter('date_from', OpenApiTypes.DATE, description='Filter logs from this date'),
        OpenApiParameter('date_to', OpenApiTypes.DATE, description='Filter logs until this date'),
        OpenApiParameter('search', OpenApiTypes.STR, description='Search in email, IP, browser, city'),
        OpenApiParameter('page', OpenApiTypes.INT, description='Page number'),
        OpenApiParameter('page_size', OpenApiTypes.INT, description='Items per page (max 200)'),
    ],
    responses={
        200: OpenApiResponse(description='Paginated list of security logs'),
        403: OpenApiResponse(description='Not superadmin or not from tenant domain')
    },
    tags=['Security']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsSuperUser])
def list_security_logs(request):
    """List all security logs with filtering and pagination"""
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    queryset = SecurityLog.objects.all()

    # Apply filters
    event_type = request.GET.get('event_type')
    if event_type:
        queryset = queryset.filter(event_type=event_type)

    user_id = request.GET.get('user_id')
    if user_id:
        queryset = queryset.filter(user_id=user_id)

    ip_address = request.GET.get('ip_address')
    if ip_address:
        queryset = queryset.filter(ip_address__icontains=ip_address)

    date_from = request.GET.get('date_from')
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)

    date_to = request.GET.get('date_to')
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)

    search = request.GET.get('search')
    if search:
        queryset = queryset.filter(
            Q(attempted_email__icontains=search) |
            Q(ip_address__icontains=search) |
            Q(browser__icontains=search) |
            Q(city__icontains=search) |
            Q(country__icontains=search)
        )

    # Paginate
    paginator = SecurityLogPagination()
    page = paginator.paginate_queryset(queryset, request)

    serializer = SecurityLogSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@extend_schema(
    operation_id='security_logs_stats',
    summary='Get Security Logs Statistics',
    description='Get security event statistics for the dashboard. Superadmin only.',
    parameters=[
        OpenApiParameter('days', OpenApiTypes.INT, description='Number of days to include (default 30)'),
    ],
    responses={
        200: OpenApiResponse(
            description='Security statistics',
            response={
                'type': 'object',
                'properties': {
                    'total_logins': {'type': 'integer'},
                    'failed_logins': {'type': 'integer'},
                    'unique_ips': {'type': 'integer'},
                    'unique_users': {'type': 'integer'},
                    'by_event_type': {'type': 'object'},
                    'by_device_type': {'type': 'object'},
                    'by_date': {'type': 'array'},
                    'recent_failed_logins': {'type': 'array'},
                    'top_ips': {'type': 'array'}
                }
            }
        ),
        403: OpenApiResponse(description='Not superadmin or not from tenant domain')
    },
    tags=['Security']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsSuperUser])
def security_logs_stats(request):
    """Get security logs statistics for dashboard"""
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    days = int(request.GET.get('days', 30))
    since_date = timezone.now() - timedelta(days=days)

    logs = SecurityLog.objects.filter(created_at__gte=since_date)

    # Basic counts
    total_logins = logs.filter(event_type='login_success').count()
    failed_logins = logs.filter(event_type='login_failed').count()
    unique_ips = logs.values('ip_address').distinct().count()
    unique_users = logs.filter(user_id__isnull=False).values('user_id').distinct().count()

    # Count by event type
    by_event_type = dict(logs.values('event_type').annotate(count=Count('id')).values_list('event_type', 'count'))

    # Count by device type
    by_device_type = dict(logs.values('device_type').annotate(count=Count('id')).values_list('device_type', 'count'))

    # Daily counts for chart
    by_date = list(
        logs.annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(
            login_success=Count('id', filter=Q(event_type='login_success')),
            login_failed=Count('id', filter=Q(event_type='login_failed')),
            logout=Count('id', filter=Q(event_type='logout'))
        )
        .order_by('date')
        .values('date', 'login_success', 'login_failed', 'logout')
    )

    # Recent failed logins
    recent_failed = logs.filter(event_type='login_failed').order_by('-created_at')[:10]
    recent_failed_data = SecurityLogSerializer(recent_failed, many=True).data

    # Top IPs by activity
    top_ips = list(
        logs.values('ip_address')
        .annotate(count=Count('id'))
        .order_by('-count')[:10]
    )

    return Response({
        'total_logins': total_logins,
        'failed_logins': failed_logins,
        'unique_ips': unique_ips,
        'unique_users': unique_users,
        'by_event_type': by_event_type,
        'by_device_type': by_device_type,
        'by_date': by_date,
        'recent_failed_logins': recent_failed_data,
        'top_ips': top_ips,
        'period_days': days
    })


@extend_schema(
    operation_id='my_security_logs',
    summary='Get My Security Logs',
    description='Get security logs for the current user.',
    parameters=[
        OpenApiParameter('page', OpenApiTypes.INT, description='Page number'),
        OpenApiParameter('page_size', OpenApiTypes.INT, description='Items per page (max 100)'),
    ],
    responses={
        200: OpenApiResponse(description='User security logs'),
        403: OpenApiResponse(description='Not from tenant domain')
    },
    tags=['Security']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def my_security_logs(request):
    """Get security logs for the current user"""
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    queryset = SecurityLog.objects.filter(user_id=request.user.id).order_by('-created_at')

    paginator = SecurityLogPagination()
    paginator.page_size = 20
    paginator.max_page_size = 100
    page = paginator.paginate_queryset(queryset, request)

    serializer = SecurityLogSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


# ============================================================
# IP Whitelist Endpoints
# ============================================================

@extend_schema(
    operation_id='list_ip_whitelist',
    summary='List IP Whitelist',
    description='Get all IP whitelist entries for the tenant. Superadmin only.',
    responses={
        200: OpenApiResponse(
            description='IP whitelist entries with tenant settings',
            response={
                'type': 'object',
                'properties': {
                    'ip_whitelist_enabled': {'type': 'boolean'},
                    'superadmin_bypass_whitelist': {'type': 'boolean'},
                    'entries': {'type': 'array'}
                }
            }
        ),
        403: OpenApiResponse(description='Not superadmin or not from tenant domain')
    },
    tags=['Security']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsSuperUser])
def list_ip_whitelist(request):
    """List all IP whitelist entries for the tenant"""
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    entries = TenantIPWhitelist.objects.filter(tenant=request.tenant).select_related('created_by')
    serializer = TenantIPWhitelistSerializer(entries, many=True)

    return Response({
        'ip_whitelist_enabled': request.tenant.ip_whitelist_enabled,
        'superadmin_bypass_whitelist': request.tenant.superadmin_bypass_whitelist,
        'entries': serializer.data
    })


@extend_schema(
    operation_id='create_ip_whitelist',
    summary='Create IP Whitelist Entry',
    description='Add a new IP address or range to the whitelist. Superadmin only.',
    request=TenantIPWhitelistSerializer,
    responses={
        201: TenantIPWhitelistSerializer,
        400: OpenApiResponse(description='Validation error'),
        403: OpenApiResponse(description='Not superadmin or not from tenant domain')
    },
    tags=['Security']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsSuperUser])
def create_ip_whitelist(request):
    """Create a new IP whitelist entry"""
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = TenantIPWhitelistSerializer(data=request.data)
    if serializer.is_valid():
        # Check for duplicates
        ip_address = serializer.validated_data['ip_address']
        cidr_notation = serializer.validated_data.get('cidr_notation', '')

        existing = TenantIPWhitelist.objects.filter(
            tenant=request.tenant,
            ip_address=ip_address,
            cidr_notation=cidr_notation
        ).exists()

        if existing:
            return Response(
                {'error': 'This IP address/range is already in the whitelist'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer.save(tenant=request.tenant, created_by=request.user)
        logger.info(f"IP whitelist entry created by {request.user.email}: {ip_address}/{cidr_notation}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='manage_ip_whitelist',
    summary='Update or Delete IP Whitelist Entry',
    description='Update or delete an IP whitelist entry. Superadmin only.',
    request=TenantIPWhitelistSerializer,
    responses={
        200: TenantIPWhitelistSerializer,
        204: OpenApiResponse(description='Entry deleted'),
        403: OpenApiResponse(description='Not superadmin or not from tenant domain'),
        404: OpenApiResponse(description='Entry not found')
    },
    tags=['Security']
)
@api_view(['PUT', 'PATCH', 'DELETE'])
@permission_classes([permissions.IsAuthenticated, IsSuperUser])
def manage_ip_whitelist(request, pk):
    """Update or delete an IP whitelist entry"""
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        entry = TenantIPWhitelist.objects.get(pk=pk, tenant=request.tenant)
    except TenantIPWhitelist.DoesNotExist:
        return Response(
            {'error': 'IP whitelist entry not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == 'DELETE':
        ip_info = f"{entry.ip_address}/{entry.cidr_notation}" if entry.cidr_notation else entry.ip_address
        entry.delete()
        logger.info(f"IP whitelist entry deleted by {request.user.email}: {ip_info}")
        return Response(status=status.HTTP_204_NO_CONTENT)

    # PUT or PATCH
    serializer = TenantIPWhitelistSerializer(entry, data=request.data, partial=(request.method == 'PATCH'))
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    operation_id='toggle_ip_whitelist',
    summary='Toggle IP Whitelist',
    description='Enable or disable IP whitelist for the tenant. Superadmin only.',
    request={
        'type': 'object',
        'properties': {
            'enabled': {'type': 'boolean', 'description': 'Whether to enable IP whitelist'},
            'superadmin_bypass': {'type': 'boolean', 'description': 'Whether superadmins can bypass whitelist'}
        }
    },
    responses={
        200: OpenApiResponse(
            description='Settings updated',
            response={
                'type': 'object',
                'properties': {
                    'ip_whitelist_enabled': {'type': 'boolean'},
                    'superadmin_bypass_whitelist': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        ),
        400: OpenApiResponse(description='Cannot enable without entries'),
        403: OpenApiResponse(description='Not superadmin or not from tenant domain')
    },
    tags=['Security']
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsSuperUser])
def toggle_ip_whitelist(request):
    """Toggle IP whitelist enabled/disabled for the tenant"""
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    tenant = request.tenant
    enabled = request.data.get('enabled')
    superadmin_bypass = request.data.get('superadmin_bypass')

    # If enabling whitelist, ensure there's at least one entry
    if enabled is True:
        active_entries = TenantIPWhitelist.objects.filter(
            tenant=tenant,
            is_active=True
        ).count()

        if active_entries == 0:
            return Response(
                {'error': 'Cannot enable IP whitelist without any active whitelist entries. Add at least one IP address first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Update settings
    if enabled is not None:
        tenant.ip_whitelist_enabled = enabled

    if superadmin_bypass is not None:
        tenant.superadmin_bypass_whitelist = superadmin_bypass

    tenant.save()

    logger.info(f"IP whitelist settings updated by {request.user.email}: enabled={tenant.ip_whitelist_enabled}, bypass={tenant.superadmin_bypass_whitelist}")

    return Response({
        'ip_whitelist_enabled': tenant.ip_whitelist_enabled,
        'superadmin_bypass_whitelist': tenant.superadmin_bypass_whitelist,
        'message': 'IP whitelist settings updated successfully'
    })


@extend_schema(
    operation_id='get_current_ip',
    summary='Get Current IP Address',
    description='Get the current request IP address and location. Useful for adding to whitelist.',
    responses={
        200: OpenApiResponse(
            description='Current IP information',
            response={
                'type': 'object',
                'properties': {
                    'ip_address': {'type': 'string'},
                    'city': {'type': 'string'},
                    'country': {'type': 'string'},
                    'country_code': {'type': 'string'}
                }
            }
        ),
        403: OpenApiResponse(description='Not from tenant domain')
    },
    tags=['Security']
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_current_ip(request):
    """Get the current request's IP address and location"""
    if not hasattr(request, 'tenant') or request.tenant.schema_name == get_public_schema_name():
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    ip_address = SecurityService.get_client_ip(request)
    location = SecurityService.get_ip_location(ip_address)

    return Response({
        'ip_address': ip_address,
        'city': location.get('city', ''),
        'country': location.get('country', ''),
        'country_code': location.get('country_code', '')
    })
