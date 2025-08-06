from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from drf_spectacular.utils import extend_schema, OpenApiResponse
from .models import Package, TenantSubscription, PricingModel
from .package_serializers import PackageSerializer, PackageListSerializer, TenantSubscriptionSerializer


class PackageViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing and retrieving packages
    Read-only for public access
    """
    queryset = Package.objects.filter(is_active=True)
    serializer_class = PackageSerializer
    permission_classes = [AllowAny]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PackageListSerializer
        return PackageSerializer
    
    def get_queryset(self):
        queryset = Package.objects.filter(is_active=True)
        pricing_model = self.request.query_params.get('pricing_model', None)
        
        if pricing_model in ['agent', 'crm']:
            queryset = queryset.filter(pricing_model=pricing_model)
        
        return queryset.order_by('pricing_model', 'sort_order', 'price_gel')


@extend_schema(
    operation_id='list_packages_by_pricing_model',
    summary='List Packages by Pricing Model',
    description='Get packages organized by pricing model (agent-based vs CRM-based)',
    responses={
        200: OpenApiResponse(
            description='Packages organized by pricing model',
            response={
                'type': 'object',
                'properties': {
                    'agent_based': {
                        'type': 'array',
                        'items': PackageListSerializer
                    },
                    'crm_based': {
                        'type': 'array', 
                        'items': PackageListSerializer
                    }
                }
            }
        )
    },
    tags=['Packages']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def list_packages_by_model(request):
    """
    List packages organized by pricing model for frontend display
    """
    agent_packages = Package.objects.filter(
        is_active=True, 
        pricing_model=PricingModel.AGENT_BASED
    ).order_by('sort_order', 'price_gel')
    
    crm_packages = Package.objects.filter(
        is_active=True,
        pricing_model=PricingModel.CRM_BASED
    ).order_by('sort_order', 'price_gel')
    
    return Response({
        'agent_based': PackageListSerializer(agent_packages, many=True).data,
        'crm_based': PackageListSerializer(crm_packages, many=True).data
    })


@extend_schema(
    operation_id='calculate_pricing',
    summary='Calculate Package Pricing',
    description='Calculate total cost for a package with specified agent count',
    responses={
        200: OpenApiResponse(
            description='Pricing calculation result',
            response={
                'type': 'object',
                'properties': {
                    'package_id': {'type': 'integer'},
                    'package_name': {'type': 'string'},
                    'pricing_model': {'type': 'string'},
                    'base_price': {'type': 'number'},
                    'agent_count': {'type': 'integer'},
                    'monthly_cost': {'type': 'number'},
                    'yearly_cost': {'type': 'number'},
                    'savings_yearly': {'type': 'number'}
                }
            }
        ),
        400: OpenApiResponse(description='Invalid package or agent count'),
        404: OpenApiResponse(description='Package not found')
    },
    tags=['Packages']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def calculate_pricing(request):
    """
    Calculate pricing for a package with specified parameters
    """
    package_id = request.query_params.get('package_id')
    agent_count = request.query_params.get('agent_count', 1)
    
    if not package_id:
        return Response({'error': 'package_id is required'}, status=400)
    
    try:
        agent_count = int(agent_count)
        if agent_count < 1:
            return Response({'error': 'agent_count must be at least 1'}, status=400)
    except ValueError:
        return Response({'error': 'agent_count must be a valid number'}, status=400)
    
    try:
        package = Package.objects.get(id=package_id, is_active=True)
    except Package.DoesNotExist:
        return Response({'error': 'Package not found'}, status=404)
    
    # Calculate costs
    if package.pricing_model == PricingModel.AGENT_BASED:
        monthly_cost = package.price_gel * agent_count
    else:
        monthly_cost = package.price_gel
        agent_count = None  # Not applicable for CRM-based
    
    yearly_cost = monthly_cost * 12
    savings_yearly = monthly_cost * 2  # Assume 2 months free for yearly
    
    return Response({
        'package_id': package.id,
        'package_name': package.display_name,
        'pricing_model': package.pricing_model,
        'base_price': float(package.price_gel),
        'agent_count': agent_count,
        'monthly_cost': float(monthly_cost),
        'yearly_cost': float(yearly_cost),
        'savings_yearly': float(savings_yearly)
    })


@extend_schema(
    operation_id='get_package_features',
    summary='Get Package Features',
    description='Get detailed feature list for a specific package',
    responses={
        200: OpenApiResponse(
            description='Package features and limits',
            response={
                'type': 'object',
                'properties': {
                    'package_id': {'type': 'integer'},
                    'package_name': {'type': 'string'},
                    'features': {
                        'type': 'array',
                        'items': {'type': 'string'}
                    },
                    'limits': {
                        'type': 'object',
                        'properties': {
                            'max_users': {'type': 'integer'},
                            'max_whatsapp_messages': {'type': 'integer'},
                            'max_storage_gb': {'type': 'integer'}
                        }
                    },
                    'capabilities': {
                        'type': 'object',
                        'properties': {
                            'ticket_management': {'type': 'boolean'},
                            'email_integration': {'type': 'boolean'},
                            'sip_calling': {'type': 'boolean'},
                            'facebook_integration': {'type': 'boolean'},
                            'instagram_integration': {'type': 'boolean'},
                            'whatsapp_integration': {'type': 'boolean'},
                            'advanced_analytics': {'type': 'boolean'},
                            'api_access': {'type': 'boolean'},
                            'custom_integrations': {'type': 'boolean'},
                            'priority_support': {'type': 'boolean'},
                            'dedicated_account_manager': {'type': 'boolean'}
                        }
                    }
                }
            }
        ),
        404: OpenApiResponse(description='Package not found')
    },
    tags=['Packages']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def get_package_features(request, package_id):
    """
    Get detailed features for a specific package
    """
    try:
        package = Package.objects.get(id=package_id, is_active=True)
    except Package.DoesNotExist:
        return Response({'error': 'Package not found'}, status=404)
    
    return Response({
        'package_id': package.id,
        'package_name': package.display_name,
        'features': package.features_list,
        'limits': {
            'max_users': package.max_users,
            'max_whatsapp_messages': package.max_whatsapp_messages,
            'max_storage_gb': package.max_storage_gb
        },
        'capabilities': {
            'ticket_management': package.ticket_management,
            'email_integration': package.email_integration,
            'sip_calling': package.sip_calling,
            'facebook_integration': package.facebook_integration,
            'instagram_integration': package.instagram_integration,
            'whatsapp_integration': package.whatsapp_integration,
            'advanced_analytics': package.advanced_analytics,
            'api_access': package.api_access,
            'custom_integrations': package.custom_integrations,
            'priority_support': package.priority_support,
            'dedicated_account_manager': package.dedicated_account_manager
        }
    })
