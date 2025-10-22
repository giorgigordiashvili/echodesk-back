"""
Payment views for subscription management
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Tenant, Package, TenantSubscription, UsageLog
from .flitt_payment import flitt_service
import logging

logger = logging.getLogger(__name__)


@extend_schema(
    operation_id='create_subscription_payment',
    summary='Create Subscription Payment',
    description='Create a payment session for subscribing to or upgrading a package',
    request={
        'type': 'object',
        'properties': {
            'package_id': {'type': 'integer'},
            'agent_count': {'type': 'integer', 'default': 1},
        },
        'required': ['package_id']
    },
    responses={
        200: OpenApiResponse(
            description='Payment session created',
            response={
                'type': 'object',
                'properties': {
                    'payment_id': {'type': 'string'},
                    'payment_url': {'type': 'string'},
                    'amount': {'type': 'number'},
                    'currency': {'type': 'string'}
                }
            }
        ),
        400: OpenApiResponse(description='Invalid request'),
        404: OpenApiResponse(description='Package not found'),
        500: OpenApiResponse(description='Payment gateway error')
    },
    tags=['Payments']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_subscription_payment(request):
    """
    Create a payment session for subscription

    For agent-based pricing, provide agent_count
    For CRM-based pricing, agent_count is ignored
    """
    if not hasattr(request, 'tenant'):
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    package_id = request.data.get('package_id')
    agent_count = request.data.get('agent_count', 1)

    if not package_id:
        return Response(
            {'error': 'package_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        package = Package.objects.get(id=package_id, is_active=True)
    except Package.DoesNotExist:
        return Response(
            {'error': 'Package not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Validate agent_count
    if package.pricing_model == 'agent':
        if agent_count < 1:
            return Response(
                {'error': 'agent_count must be at least 1'},
                status=status.HTTP_400_BAD_REQUEST
            )
    else:
        agent_count = 1  # Not applicable for CRM-based

    # Check if Flitt is configured
    if not flitt_service.is_configured():
        return Response(
            {
                'error': 'Payment gateway not configured',
                'message': 'Please contact support to set up payment processing'
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    # Generate URLs
    base_url = f"https://{request.get_host()}"
    return_url = f"{base_url}/settings/subscription/success"
    callback_url = f"{settings.API_DOMAIN}/api/payments/webhook/"

    try:
        # Create payment session
        payment_result = flitt_service.create_subscription_payment(
            tenant=request.tenant,
            package=package,
            agent_count=agent_count,
            return_url=return_url,
            callback_url=callback_url
        )

        return Response({
            'payment_id': payment_result.get('payment_id'),
            'payment_url': payment_result.get('payment_url'),
            'amount': payment_result.get('amount'),
            'currency': payment_result.get('currency', 'GEL'),
            'status': 'pending'
        })

    except Exception as e:
        logger.error(f'Failed to create payment for tenant {request.tenant.schema_name}: {e}')
        return Response(
            {
                'error': 'Payment creation failed',
                'message': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    operation_id='check_payment_status',
    summary='Check Payment Status',
    description='Check the status of a payment transaction',
    responses={
        200: OpenApiResponse(
            description='Payment status',
            response={
                'type': 'object',
                'properties': {
                    'payment_id': {'type': 'string'},
                    'status': {'type': 'string'},
                    'amount': {'type': 'number'},
                    'paid': {'type': 'boolean'}
                }
            }
        ),
        404: OpenApiResponse(description='Payment not found')
    },
    tags=['Payments']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_payment_status(request, payment_id):
    """
    Check the status of a payment
    """
    if not flitt_service.is_configured():
        return Response(
            {'error': 'Payment gateway not configured'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    try:
        payment_status = flitt_service.check_payment_status(payment_id)
        return Response(payment_status)

    except Exception as e:
        logger.error(f'Failed to check payment status for {payment_id}: {e}')
        return Response(
            {'error': 'Failed to check payment status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    operation_id='flitt_webhook',
    summary='Flitt Payment Webhook',
    description='Webhook endpoint for receiving payment status updates from Flitt',
    responses={
        200: OpenApiResponse(description='Webhook processed successfully'),
        400: OpenApiResponse(description='Invalid signature or payload')
    },
    tags=['Payments']
)
@api_view(['POST'])
@permission_classes([AllowAny])  # Webhook from Flitt, no auth
def flitt_webhook(request):
    """
    Handle webhook notifications from Flitt payment gateway

    This endpoint processes payment status updates and creates/updates subscriptions
    """
    # Verify webhook signature
    signature = request.headers.get('X-Flitt-Signature', '')
    if not signature:
        logger.warning('Webhook received without signature')
        return Response(
            {'error': 'Missing signature'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not flitt_service.verify_webhook_signature(request.data, signature):
        logger.warning('Invalid webhook signature')
        return Response(
            {'error': 'Invalid signature'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Process payment event
    event_type = request.data.get('event')
    payment_data = request.data.get('payment', {})
    payment_id = payment_data.get('id')
    payment_status = payment_data.get('status')
    metadata = payment_data.get('metadata', {})

    logger.info(f'Webhook received: event={event_type}, payment={payment_id}, status={payment_status}')

    # Handle successful payment
    if event_type == 'payment.succeeded' or payment_status == 'paid':
        try:
            # Extract metadata
            tenant_id = metadata.get('tenant_id')
            package_id = metadata.get('package_id')
            agent_count = metadata.get('agent_count', 1)

            if not all([tenant_id, package_id]):
                logger.error('Missing tenant_id or package_id in webhook metadata')
                return Response(
                    {'error': 'Invalid metadata'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get tenant and package
            tenant = Tenant.objects.get(id=tenant_id)
            package = Package.objects.get(id=package_id)

            # Create or update subscription
            subscription, created = TenantSubscription.objects.update_or_create(
                tenant=tenant,
                defaults={
                    'package': package,
                    'is_active': True,
                    'starts_at': timezone.now(),
                    'expires_at': timezone.now() + timedelta(days=30),  # 30 days subscription
                    'agent_count': agent_count,
                    'last_billed_at': timezone.now(),
                    'next_billing_date': timezone.now() + timedelta(days=30)
                }
            )

            # Log the event
            UsageLog.objects.create(
                subscription=subscription,
                event_type='feature_used',
                quantity=1,
                metadata={
                    'event': 'subscription_payment',
                    'payment_id': payment_id,
                    'amount': payment_data.get('amount'),
                    'action': 'created' if created else 'renewed'
                }
            )

            logger.info(f'Subscription {"created" if created else "updated"} for tenant {tenant.schema_name}')

            return Response({'status': 'success', 'action': 'created' if created else 'renewed'})

        except Tenant.DoesNotExist:
            logger.error(f'Tenant not found: {tenant_id}')
            return Response({'error': 'Tenant not found'}, status=status.HTTP_404_NOT_FOUND)

        except Package.DoesNotExist:
            logger.error(f'Package not found: {package_id}')
            return Response({'error': 'Package not found'}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f'Error processing webhook: {e}')
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Handle failed payment
    elif event_type == 'payment.failed' or payment_status == 'failed':
        logger.warning(f'Payment failed: {payment_id}')
        # Optionally notify tenant admin
        # send_payment_failed_notification(metadata.get('tenant_id'))

    return Response({'status': 'received'})


@extend_schema(
    operation_id='cancel_subscription',
    summary='Cancel Subscription',
    description='Cancel the current subscription',
    responses={
        200: OpenApiResponse(description='Subscription cancelled'),
        404: OpenApiResponse(description='No active subscription found')
    },
    tags=['Payments']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_subscription(request):
    """
    Cancel the current subscription

    NOTE: This only deactivates the subscription, doesn't process refunds
    For refunds, contact admin
    """
    if not hasattr(request, 'tenant'):
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        subscription = TenantSubscription.objects.get(tenant=request.tenant, is_active=True)
        subscription.is_active = False
        subscription.save()

        logger.info(f'Subscription cancelled for tenant {request.tenant.schema_name}')

        return Response({
            'status': 'cancelled',
            'message': 'Your subscription has been cancelled. You will retain access until the end of your billing period.'
        })

    except TenantSubscription.DoesNotExist:
        return Response(
            {'error': 'No active subscription found'},
            status=status.HTTP_404_NOT_FOUND
        )
