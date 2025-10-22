"""
Subscription-based permission system for EchoDesk

This module provides decorators and utilities to check tenant subscription features
and enforce access control based on the tenant's active package.

Usage:
    @require_subscription_feature('sip_calling')
    def make_call(request):
        # This view is only accessible if tenant's package has sip_calling=True
        ...

    # Or check manually in views:
    if has_subscription_feature(request, 'whatsapp_integration'):
        # Allow WhatsApp message sending
        ...
"""

from functools import wraps
from django.http import JsonResponse
from rest_framework.response import Response
from rest_framework import status
from tenant_schemas.utils import get_public_schema_name


class SubscriptionFeature:
    """Feature constants for subscription packages"""
    TICKET_MANAGEMENT = 'ticket_management'
    EMAIL_INTEGRATION = 'email_integration'
    SIP_CALLING = 'sip_calling'
    FACEBOOK_INTEGRATION = 'facebook_integration'
    INSTAGRAM_INTEGRATION = 'instagram_integration'
    WHATSAPP_INTEGRATION = 'whatsapp_integration'
    ADVANCED_ANALYTICS = 'advanced_analytics'
    API_ACCESS = 'api_access'
    CUSTOM_INTEGRATIONS = 'custom_integrations'
    PRIORITY_SUPPORT = 'priority_support'
    DEDICATED_ACCOUNT_MANAGER = 'dedicated_account_manager'


def get_tenant_subscription(request):
    """
    Get the tenant's active subscription from the request

    Args:
        request: Django request object with tenant attached

    Returns:
        TenantSubscription object or None
    """
    if not hasattr(request, 'tenant'):
        return None

    # Skip for public schema
    if request.tenant.schema_name == get_public_schema_name():
        return None

    try:
        subscription = request.tenant.subscription
        if subscription.is_active:
            return subscription
    except Exception:
        pass

    return None


def has_subscription_feature(request, feature_name):
    """
    Check if the tenant's subscription includes a specific feature

    Args:
        request: Django request object
        feature_name: Name of the feature to check (e.g., 'sip_calling')

    Returns:
        bool: True if feature is enabled, False otherwise
    """
    subscription = get_tenant_subscription(request)

    if not subscription:
        return False

    package = subscription.package
    return getattr(package, feature_name, False)


def check_subscription_limit(request, limit_type):
    """
    Check if tenant has reached a specific usage limit

    Args:
        request: Django request object
        limit_type: 'users', 'whatsapp', or 'storage'

    Returns:
        dict: {
            'within_limit': bool,
            'current': int,
            'limit': int,
            'usage_percentage': float
        }
    """
    subscription = get_tenant_subscription(request)

    if not subscription:
        return {
            'within_limit': False,
            'current': 0,
            'limit': 0,
            'usage_percentage': 0,
            'error': 'No active subscription'
        }

    if limit_type == 'users':
        current = subscription.current_users
        limit = subscription.package.max_users or float('inf')
        within_limit = subscription.can_add_user()
    elif limit_type == 'whatsapp':
        current = subscription.whatsapp_messages_used
        limit = subscription.package.max_whatsapp_messages
        within_limit = subscription.can_send_whatsapp_message()
    elif limit_type == 'storage':
        current = float(subscription.storage_used_gb)
        limit = subscription.package.max_storage_gb
        within_limit = not subscription.is_over_storage_limit
    else:
        return {
            'within_limit': False,
            'current': 0,
            'limit': 0,
            'usage_percentage': 0,
            'error': 'Invalid limit type'
        }

    usage_percentage = (current / limit * 100) if limit and limit != float('inf') else 0

    return {
        'within_limit': within_limit,
        'current': current,
        'limit': limit if limit != float('inf') else None,
        'usage_percentage': round(usage_percentage, 2)
    }


def get_subscription_info(request):
    """
    Get complete subscription information for the tenant

    Args:
        request: Django request object

    Returns:
        dict: Complete subscription details including features, limits, and usage
    """
    subscription = get_tenant_subscription(request)

    if not subscription:
        return {
            'has_subscription': False,
            'error': 'No active subscription found'
        }

    package = subscription.package

    return {
        'has_subscription': True,
        'package': {
            'id': package.id,
            'name': package.display_name,
            'pricing_model': package.get_pricing_model_display(),
        },
        'subscription': {
            'is_active': subscription.is_active,
            'starts_at': subscription.starts_at,
            'expires_at': subscription.expires_at,
            'monthly_cost': float(subscription.monthly_cost),
            'agent_count': subscription.agent_count,
        },
        'features': {
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
            'dedicated_account_manager': package.dedicated_account_manager,
        },
        'limits': {
            'max_users': package.max_users,
            'max_whatsapp_messages': package.max_whatsapp_messages,
            'max_storage_gb': package.max_storage_gb,
        },
        'usage': {
            'current_users': subscription.current_users,
            'whatsapp_messages_used': subscription.whatsapp_messages_used,
            'storage_used_gb': float(subscription.storage_used_gb),
        },
        'usage_limits': {
            'users': check_subscription_limit(request, 'users'),
            'whatsapp': check_subscription_limit(request, 'whatsapp'),
            'storage': check_subscription_limit(request, 'storage'),
        }
    }


# Decorators for Django views and DRF views

def require_subscription_feature(feature_name, error_message=None):
    """
    Decorator to require a specific subscription feature for a view

    Usage:
        @require_subscription_feature('sip_calling')
        def make_call(request):
            ...

    Args:
        feature_name: Name of the required feature
        error_message: Custom error message (optional)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not has_subscription_feature(request, feature_name):
                message = error_message or f"Your subscription does not include access to {feature_name.replace('_', ' ')}"

                # Check if it's a DRF view (has .data attribute)
                if hasattr(request, 'accepted_renderer'):
                    return Response(
                        {'error': message, 'feature_required': feature_name},
                        status=status.HTTP_403_FORBIDDEN
                    )

                # Django view
                return JsonResponse(
                    {'error': message, 'feature_required': feature_name},
                    status=403
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view
    return decorator


def require_subscription_limit(limit_type, error_message=None):
    """
    Decorator to check if tenant is within usage limits

    Usage:
        @require_subscription_limit('users')
        def add_user(request):
            ...

    Args:
        limit_type: Type of limit to check ('users', 'whatsapp', 'storage')
        error_message: Custom error message (optional)
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            limit_check = check_subscription_limit(request, limit_type)

            if not limit_check.get('within_limit', False):
                message = error_message or f"You have reached your {limit_type} limit"

                # Check if it's a DRF view
                if hasattr(request, 'accepted_renderer'):
                    return Response(
                        {
                            'error': message,
                            'limit_type': limit_type,
                            'limit_details': limit_check
                        },
                        status=status.HTTP_403_FORBIDDEN
                    )

                # Django view
                return JsonResponse(
                    {
                        'error': message,
                        'limit_type': limit_type,
                        'limit_details': limit_check
                    },
                    status=403
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view
    return decorator


def require_active_subscription(view_func):
    """
    Decorator to require an active subscription for a view

    Usage:
        @require_active_subscription
        def protected_view(request):
            ...
    """
    @wraps(view_func)
    def wrapped_view(request, *args, **kwargs):
        subscription = get_tenant_subscription(request)

        if not subscription:
            message = "No active subscription found. Please upgrade your account."

            # Check if it's a DRF view
            if hasattr(request, 'accepted_renderer'):
                return Response(
                    {'error': message},
                    status=status.HTTP_402_PAYMENT_REQUIRED
                )

            # Django view
            return JsonResponse(
                {'error': message},
                status=402
            )

        return view_func(request, *args, **kwargs)

    return wrapped_view


# DRF Permission Classes

from rest_framework.permissions import BasePermission


class HasSubscriptionFeature(BasePermission):
    """
    DRF Permission class to check subscription features

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            permission_classes = [HasSubscriptionFeature]
            required_feature = 'sip_calling'
    """
    required_feature = None

    def has_permission(self, request, view):
        # Allow if no feature specified
        if not self.required_feature:
            return True

        # Get feature from view if not set on permission class
        feature = getattr(view, 'required_feature', self.required_feature)

        if not feature:
            return True

        return has_subscription_feature(request, feature)

    def get_message(self):
        feature = self.required_feature or 'this feature'
        return f"Your subscription does not include access to {feature.replace('_', ' ')}"


class WithinSubscriptionLimit(BasePermission):
    """
    DRF Permission class to check subscription limits

    Usage:
        class AddUserView(APIView):
            permission_classes = [WithinSubscriptionLimit]
            limit_type = 'users'
    """
    limit_type = None

    def has_permission(self, request, view):
        # Allow if no limit type specified
        if not self.limit_type:
            return True

        # Get limit type from view if not set on permission class
        limit = getattr(view, 'limit_type', self.limit_type)

        if not limit:
            return True

        limit_check = check_subscription_limit(request, limit)
        return limit_check.get('within_limit', False)

    def get_message(self):
        limit = self.limit_type or 'usage'
        return f"You have reached your {limit} limit"


class HasActiveSubscription(BasePermission):
    """
    DRF Permission class to require active subscription

    Usage:
        class MyViewSet(viewsets.ModelViewSet):
            permission_classes = [IsAuthenticated, HasActiveSubscription]
    """
    message = "No active subscription found"

    def has_permission(self, request, view):
        return get_tenant_subscription(request) is not None
