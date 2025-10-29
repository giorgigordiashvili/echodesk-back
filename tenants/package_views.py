from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.db import transaction
from .models import Package, TenantSubscription, PricingModel, PackageFeature, Feature
from .package_serializers import PackageSerializer, PackageListSerializer, TenantSubscriptionSerializer
from .permissions import get_subscription_info


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
            response=PackageListSerializer(many=True)
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


@extend_schema(
    operation_id='get_my_subscription',
    summary='Get Current Tenant Subscription',
    description='Get complete subscription information for the current tenant including features, limits, and usage',
    responses={
        200: OpenApiResponse(
            description='Subscription information',
            response={
                'type': 'object',
                'properties': {
                    'has_subscription': {'type': 'boolean'},
                    'package': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer'},
                            'name': {'type': 'string'},
                            'pricing_model': {'type': 'string'}
                        }
                    },
                    'subscription': {
                        'type': 'object',
                        'properties': {
                            'is_active': {'type': 'boolean'},
                            'starts_at': {'type': 'string', 'format': 'date-time'},
                            'expires_at': {'type': 'string', 'format': 'date-time'},
                            'monthly_cost': {'type': 'number'},
                            'agent_count': {'type': 'integer'}
                        }
                    },
                    'features': {'type': 'object'},
                    'limits': {'type': 'object'},
                    'usage': {'type': 'object'},
                    'usage_limits': {'type': 'object'}
                }
            }
        ),
        403: OpenApiResponse(description='Access from public schema not allowed'),
        404: OpenApiResponse(description='No active subscription found')
    },
    tags=['Subscriptions']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_subscription(request):
    """
    Get subscription information for the current tenant
    Includes package details, features, limits, and current usage
    """
    subscription_info = get_subscription_info(request)

    if not subscription_info.get('has_subscription'):
        return Response(
            {'error': subscription_info.get('error', 'No active subscription found')},
            status=status.HTTP_404_NOT_FOUND
        )

    return Response(subscription_info)


@extend_schema(
    operation_id='calculate_custom_package_price',
    summary='Calculate Custom Package Price',
    description='Calculate total price based on selected features',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'feature_ids': {
                    'type': 'array',
                    'items': {'type': 'integer'},
                    'description': 'Array of feature IDs to include in custom package'
                }
            },
            'required': ['feature_ids']
        }
    },
    responses={
        200: OpenApiResponse(
            description='Calculated price',
            response={
                'type': 'object',
                'properties': {
                    'features': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer'},
                                'name': {'type': 'string'},
                                'price_gel': {'type': 'string'}
                            }
                        }
                    },
                    'total_price': {'type': 'string'},
                    'currency': {'type': 'string'}
                }
            }
        ),
        400: OpenApiResponse(description='Invalid feature IDs')
    },
    tags=['Packages']
)
@api_view(['POST'])
@permission_classes([AllowAny])
def calculate_custom_package_price(request):
    """
    Calculate price for a custom package based on selected features

    POST /api/packages/calculate-custom-price/
    Body: {
        "feature_ids": [1, 2, 3],
        "pricing_model": "agent" or "crm",  // Required
        "user_count": 10,  // Required for agent-based
        "max_users": 50  // Required for CRM-based (to set limits)
    }
    """
    feature_ids = request.data.get('feature_ids', [])
    pricing_model = request.data.get('pricing_model')  # 'agent' or 'crm'
    user_count = request.data.get('user_count')  # For agent-based
    max_users = request.data.get('max_users')  # For CRM-based limits

    if not feature_ids or not isinstance(feature_ids, list):
        return Response({
            'error': 'feature_ids must be a non-empty array'
        }, status=400)

    if pricing_model not in ['agent', 'crm']:
        return Response({
            'error': 'pricing_model must be either "agent" or "crm"'
        }, status=400)

    # Get features
    features = Feature.objects.filter(
        id__in=feature_ids,
        is_active=True
    )

    if not features.exists():
        return Response({
            'error': 'No valid features found'
        }, status=400)

    # Calculate total based on pricing model
    subtotal = 0
    features_data = []

    for feature in features:
        # Agent-based: per-user pricing
        if pricing_model == 'agent':
            if not user_count:
                return Response({
                    'error': 'user_count is required for agent-based pricing'
                }, status=400)
            feature_price = feature.price_per_user_gel * user_count
            pricing_type = 'per_user'

        # CRM-based: unlimited pricing
        else:
            feature_price = feature.price_unlimited_gel
            pricing_type = 'unlimited'

        subtotal += feature_price

        features_data.append({
            'id': feature.id,
            'key': feature.key,
            'name': feature.name,
            'description': feature.description,
            'category': feature.category,
            'category_display': feature.get_category_display(),
            'icon': feature.icon,
            'price_per_user_gel': str(feature.price_per_user_gel),
            'price_unlimited_gel': str(feature.price_unlimited_gel),
            'calculated_price': str(feature_price),
            'pricing_type': pricing_type
        })

    # No discount applied
    total_price = subtotal

    return Response({
        'features': features_data,
        'total_price': str(total_price),
        'pricing_model': pricing_model,
        'user_count': user_count if pricing_model == 'agent' else None,
        'max_users': max_users if pricing_model == 'crm' else None,
        'currency': 'GEL'
    })


@extend_schema(
    operation_id='list_available_features',
    summary='List Available Features for Custom Package',
    description='Get all available features with prices for building custom packages',
    responses={
        200: OpenApiResponse(
            description='List of available features grouped by category',
            response={
                'type': 'object',
                'properties': {
                    'categories': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'category': {'type': 'string'},
                                'category_display': {'type': 'string'},
                                'features': {
                                    'type': 'array',
                                    'items': {
                                        'type': 'object',
                                        'properties': {
                                            'id': {'type': 'integer'},
                                            'key': {'type': 'string'},
                                            'name': {'type': 'string'},
                                            'description': {'type': 'string'},
                                            'icon': {'type': 'string'},
                                            'price_gel': {'type': 'string'}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        )
    },
    tags=['Packages']
)
@api_view(['GET'])
@permission_classes([AllowAny])
def list_available_features(request):
    """
    List all available features for building custom packages

    Features are grouped by category
    """
    from .feature_models import FeatureCategory

    features = Feature.objects.filter(is_active=True).order_by('category', 'sort_order', 'name')

    # Group by category
    categories_dict = {}
    for feature in features:
        if feature.category not in categories_dict:
            categories_dict[feature.category] = {
                'category': feature.category,
                'category_display': feature.get_category_display(),
                'features': []
            }

        categories_dict[feature.category]['features'].append({
            'id': feature.id,
            'key': feature.key,
            'name': feature.name,
            'description': feature.description,
            'icon': feature.icon,
            'price_per_user_gel': str(feature.price_per_user_gel),
            'price_unlimited_gel': str(feature.price_unlimited_gel),
            'sort_order': feature.sort_order
        })

    # Convert to list
    categories_list = list(categories_dict.values())

    return Response({
        'categories': categories_list
    })
