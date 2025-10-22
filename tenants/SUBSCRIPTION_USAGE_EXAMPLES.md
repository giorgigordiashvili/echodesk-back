# Subscription Permission System - Usage Examples

This document provides examples of how to use the subscription-based permission system in EchoDesk.

## Table of Contents

1. [Setup](#setup)
2. [Using Decorators](#using-decorators)
3. [Using DRF Permission Classes](#using-drf-permission-classes)
4. [Manual Permission Checks](#manual-permission-checks)
5. [Using Middleware](#using-middleware)
6. [Admin Interface](#admin-interface)

---

## Setup

### 1. Add Subscription Middleware

Add the middleware to your `settings.py`:

```python
MIDDLEWARE = [
    'amanati_crm.middleware.EchoDeskTenantMiddleware',  # Must be first
    'tenants.subscription_middleware.SubscriptionMiddleware',  # Add this
    'amanati_crm.middleware.RequestLoggingMiddleware',
    # ... rest of middleware
]
```

### 2. Create Packages in Admin

Go to Django Admin → Packages and create your subscription tiers:
- Essential: Basic features, 5₾/agent/month
- Professional: More features, 15₾/agent/month
- Enterprise: All features, 25₾/agent/month

### 3. Assign Subscriptions to Tenants

Go to Django Admin → Tenants → Select a tenant → Use the inline form to create/edit subscription

---

## Using Decorators

### 1. Require a Specific Feature

```python
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from tenants.permissions import require_subscription_feature

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_subscription_feature('sip_calling')
def make_call(request):
    """
    This endpoint is only accessible if the tenant's subscription
    includes the 'sip_calling' feature
    """
    phone_number = request.data.get('phone_number')

    # Make the call
    result = initiate_call(phone_number)

    return Response({'status': 'calling', 'call_id': result.id})
```

### 2. Check Usage Limits

```python
from tenants.permissions import require_subscription_limit

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@require_subscription_limit('users')
def add_user(request):
    """
    This endpoint checks if the tenant can add more users
    based on their subscription limit
    """
    email = request.data.get('email')

    # Create the user
    user = User.objects.create(email=email)

    # Update usage counter
    subscription = request.tenant.subscription
    subscription.current_users += 1
    subscription.save()

    return Response({'user_id': user.id})
```

### 3. Require Active Subscription

```python
from tenants.permissions import require_active_subscription

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@require_active_subscription
def premium_report(request):
    """
    This endpoint requires any active subscription
    """
    data = generate_premium_report()
    return Response(data)
```

### 4. Custom Error Messages

```python
@require_subscription_feature(
    'advanced_analytics',
    error_message="Please upgrade to Professional or Enterprise to access advanced analytics"
)
def advanced_analytics_view(request):
    # View logic here
    pass
```

---

## Using DRF Permission Classes

### 1. ViewSet with Feature Check

```python
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from tenants.permissions import HasSubscriptionFeature

class CallHistoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet that requires 'sip_calling' feature
    """
    permission_classes = [IsAuthenticated, HasSubscriptionFeature]
    required_feature = 'sip_calling'

    def get_queryset(self):
        return CallHistory.objects.filter(tenant=self.request.tenant)
```

### 2. APIView with Limit Check

```python
from rest_framework.views import APIView
from tenants.permissions import WithinSubscriptionLimit

class SendWhatsAppMessageView(APIView):
    """
    View that checks WhatsApp message limits
    """
    permission_classes = [IsAuthenticated, WithinSubscriptionLimit]
    limit_type = 'whatsapp'

    def post(self, request):
        # Send WhatsApp message
        send_whatsapp_message(request.data['message'])

        # Update usage counter
        subscription = request.tenant.subscription
        subscription.whatsapp_messages_used += 1
        subscription.save()

        return Response({'status': 'sent'})
```

### 3. Multiple Permission Classes

```python
class AdvancedAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, HasActiveSubscription]
    required_feature = 'advanced_analytics'

    def get(self, request):
        # Return advanced analytics data
        pass
```

---

## Manual Permission Checks

### 1. Check Feature in View

```python
from tenants.permissions import has_subscription_feature

@api_view(['GET'])
def dashboard(request):
    """
    Dashboard with conditional features based on subscription
    """
    data = {
        'basic_stats': get_basic_stats(),
    }

    # Only include advanced analytics if available
    if has_subscription_feature(request, 'advanced_analytics'):
        data['advanced_analytics'] = get_advanced_analytics()

    # Only include call stats if SIP calling is enabled
    if has_subscription_feature(request, 'sip_calling'):
        data['call_stats'] = get_call_statistics()

    return Response(data)
```

### 2. Check Limit Status

```python
from tenants.permissions import check_subscription_limit

@api_view(['GET'])
def usage_status(request):
    """
    Get current usage status for all limits
    """
    return Response({
        'users': check_subscription_limit(request, 'users'),
        'whatsapp': check_subscription_limit(request, 'whatsapp'),
        'storage': check_subscription_limit(request, 'storage'),
    })
```

### 3. Get Complete Subscription Info

```python
from tenants.permissions import get_subscription_info

@api_view(['GET'])
def subscription_details(request):
    """
    Get complete subscription information
    """
    info = get_subscription_info(request)
    return Response(info)
```

---

## Using Middleware

Once you've added `SubscriptionMiddleware` to your settings, every request will have subscription information attached:

### 1. Access Subscription Object

```python
@api_view(['GET'])
def my_view(request):
    # Access subscription object directly
    subscription = request.subscription

    if subscription:
        package = request.subscription_package
        print(f"Package: {package.display_name}")
        print(f"Monthly cost: {subscription.monthly_cost}")
```

### 2. Access Features Dictionary

```python
@api_view(['GET'])
def feature_check(request):
    # Access features dictionary
    features = request.subscription_features

    if features.get('sip_calling'):
        # SIP calling is enabled
        pass
```

### 3. Use Helper Method

```python
@api_view(['POST'])
def conditional_action(request):
    # Use the helper method attached by middleware
    if request.has_feature('whatsapp_integration'):
        # Send WhatsApp notification
        send_whatsapp_notification()

    if request.has_feature('email_integration'):
        # Send email notification
        send_email_notification()
```

---

## Admin Interface

### Managing Subscriptions

1. **View All Subscriptions**
   - Go to Admin → Tenant Subscriptions
   - See status badges, usage indicators, and monthly costs

2. **Create Subscription for Tenant**
   - Go to Admin → Tenants → Select tenant
   - Use the inline form at the bottom to create/edit subscription
   - Or use the action: "Create basic subscription for selected tenants"

3. **Admin Actions**
   - **Activate/Deactivate**: Bulk activate or deactivate subscriptions
   - **Reset Usage**: Reset WhatsApp and storage usage counters
   - **Extend Subscription**: Extend expiry date by 30 days

4. **View Subscription Details**
   - Click on any tenant to see detailed subscription info
   - View features, limits, and usage statistics
   - Color-coded indicators show when limits are exceeded

---

## Best Practices

### 1. Always Update Usage Counters

```python
@require_subscription_limit('whatsapp')
def send_whatsapp(request):
    # Send message
    send_message()

    # IMPORTANT: Update counter
    subscription = request.tenant.subscription
    subscription.whatsapp_messages_used += 1
    subscription.save()

    # Or use UsageLog for detailed tracking
    from tenants.models import UsageLog
    UsageLog.objects.create(
        subscription=subscription,
        event_type='whatsapp_message',
        quantity=1,
        metadata={'recipient': request.data['phone']}
    )
```

### 2. Provide Helpful Error Messages

```python
from rest_framework.exceptions import PermissionDenied

if not has_subscription_feature(request, 'api_access'):
    raise PermissionDenied(
        "API access is not included in your plan. "
        "Upgrade to Professional or Enterprise to enable API access."
    )
```

### 3. Log Feature Usage

```python
from tenants.models import UsageLog

if has_subscription_feature(request, 'advanced_analytics'):
    # Log the usage
    UsageLog.objects.create(
        subscription=request.tenant.subscription,
        event_type='feature_used',
        metadata={'feature': 'advanced_analytics'}
    )

    # Provide the feature
    return get_advanced_analytics()
```

### 4. Check Limits Before Actions

```python
def add_user_to_system(request, user_data):
    # Check limit first
    limit_check = check_subscription_limit(request, 'users')

    if not limit_check['within_limit']:
        return Response({
            'error': 'User limit reached',
            'current': limit_check['current'],
            'limit': limit_check['limit'],
            'usage_percentage': limit_check['usage_percentage'],
            'upgrade_message': 'Please upgrade your plan to add more users'
        }, status=403)

    # Create user
    create_user(user_data)
```

---

## Available Features

Feature flags that can be checked:

- `ticket_management` - Complete ticket management system
- `email_integration` - Email integration
- `sip_calling` - Integrated SIP phone system
- `facebook_integration` - Facebook Messenger integration
- `instagram_integration` - Instagram DM integration
- `whatsapp_integration` - WhatsApp Business API
- `advanced_analytics` - Advanced analytics dashboard
- `api_access` - API access
- `custom_integrations` - Custom integrations
- `priority_support` - Priority support
- `dedicated_account_manager` - Dedicated account manager

---

## Available Limits

Limit types that can be checked:

- `users` - Maximum number of users
- `whatsapp` - WhatsApp messages per month
- `storage` - Storage in GB

---

## Testing

### Test Subscription Features

```python
from django.test import TestCase
from tenants.models import Tenant, Package, TenantSubscription
from django.utils import timezone

class SubscriptionTestCase(TestCase):
    def setUp(self):
        # Create package
        self.package = Package.objects.create(
            name='test_package',
            display_name='Test Package',
            price_gel=10,
            max_users=5,
            sip_calling=True,
            whatsapp_integration=False
        )

        # Create tenant
        self.tenant = Tenant.objects.create(
            schema_name='test',
            name='Test Tenant'
        )

        # Create subscription
        self.subscription = TenantSubscription.objects.create(
            tenant=self.tenant,
            package=self.package,
            is_active=True,
            starts_at=timezone.now()
        )

    def test_feature_access(self):
        # SIP calling should be enabled
        self.assertTrue(self.package.sip_calling)

        # WhatsApp should be disabled
        self.assertFalse(self.package.whatsapp_integration)

    def test_user_limit(self):
        # Should allow adding users up to limit
        self.assertTrue(self.subscription.can_add_user())

        # Set users to limit
        self.subscription.current_users = 5

        # Should not allow more users
        self.assertFalse(self.subscription.can_add_user())
```

---

## Support

For questions or issues with the subscription system:
1. Check this documentation
2. Review the code in `tenants/permissions.py`
3. Check admin interface for subscription status
4. Contact support team
