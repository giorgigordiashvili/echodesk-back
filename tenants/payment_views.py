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
from .models import Tenant, Package, TenantSubscription, UsageLog, PaymentOrder, PendingRegistration
from .bog_payment import bog_service
from .services import SingleFrontendDeploymentService
from tenant_schemas.utils import schema_context
from django.contrib.auth import get_user_model
from django.db import transaction
import logging

User = get_user_model()

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

    # Check if BOG is configured
    if not bog_service.is_configured():
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
        # Generate external order ID
        import uuid
        external_order_id = f"SUB-{uuid.uuid4().hex[:12].upper()}"

        # Create payment session
        payment_result = bog_service.create_subscription_payment(
            tenant=request.tenant,
            package=package,
            agent_count=agent_count,
            return_url_success=return_url,
            return_url_fail=f"{base_url}/settings/subscription/failed",
            callback_url=callback_url,
            external_order_id=external_order_id
        )

        # Store payment order in database
        payment_order = PaymentOrder.objects.create(
            order_id=payment_result['order_id'],
            tenant=request.tenant,
            package=package,
            amount=payment_result['amount'],
            currency=payment_result['currency'],
            agent_count=agent_count,
            payment_url=payment_result['payment_url'],
            status='pending',
            metadata=payment_result.get('metadata', {})
        )

        logger.info(f'Payment order created: {payment_order.order_id} for tenant {request.tenant.schema_name}')

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
    if not bog_service.is_configured():
        return Response(
            {'error': 'Payment gateway not configured'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    try:
        payment_status = bog_service.check_payment_status(payment_id)
        return Response(payment_status)

    except Exception as e:
        logger.error(f'Failed to check payment status for {payment_id}: {e}')
        return Response(
            {'error': 'Failed to check payment status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    operation_id='bog_webhook',
    summary='BOG Payment Webhook',
    description='Webhook endpoint for receiving payment status updates from Bank of Georgia',
    responses={
        200: OpenApiResponse(description='Webhook processed successfully'),
        400: OpenApiResponse(description='Invalid signature or payload')
    },
    tags=['Payments']
)
@api_view(['POST'])
@permission_classes([AllowAny])  # Webhook from BOG, no auth
def bog_webhook(request):
    """
    Handle webhook notifications from Bank of Georgia payment gateway

    This endpoint processes payment status updates and creates/updates subscriptions

    BOG Callback format:
    {
        "event": "order_payment",
        "zoned_request_time": "2024-01-01T12:00:00.000000Z",
        "body": {
            "order_id": "...",
            "order_status": {"key": "completed", ...},
            ...
        }
    }
    """
    # Optional: Verify webhook signature
    signature = request.headers.get('Callback-Signature', '')
    if signature:
        # TODO: Implement signature verification when BOG provides public key
        # bog_service.verify_webhook_signature(request.body, signature)
        logger.info('Webhook signature received (verification not implemented)')

    # Process payment event
    event_type = request.data.get('event')
    body = request.data.get('body', {})

    if event_type != 'order_payment':
        logger.warning(f'Unexpected webhook event type: {event_type}')
        return Response({'error': 'Unexpected event type'}, status=status.HTTP_400_BAD_REQUEST)

    order_id = body.get('order_id') or body.get('id')
    order_status_obj = body.get('order_status', {})
    bog_status = order_status_obj.get('key', '')
    response_code = body.get('code', '')
    transaction_id = body.get('transaction_id', '')

    logger.info(f'BOG webhook received: order_id={order_id}, status={bog_status}, code={response_code}')

    # Handle successful payment (BOG status: 'completed' with response code '100')
    if bog_status == 'completed' and response_code == '100':
        try:
            # Get payment order from database using order_id
            if not order_id:
                logger.error('Missing order_id in webhook payload')
                return Response({'error': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                payment_order = PaymentOrder.objects.get(order_id=order_id)
            except PaymentOrder.DoesNotExist:
                logger.error(f'Payment order not found: {order_id}')
                return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

            # Update payment order status
            payment_order.status = 'paid'
            payment_order.paid_at = timezone.now()
            payment_order.save()

            # Check if this is a registration payment (no tenant yet)
            if payment_order.tenant is None:
                # This is a registration payment - create tenant from pending registration
                try:
                    pending_registration = PendingRegistration.objects.get(
                        order_id=order_id,
                        is_processed=False
                    )
                except PendingRegistration.DoesNotExist:
                    logger.error(f'Pending registration not found for order: {order_id}')
                    return Response({'error': 'Registration not found'}, status=status.HTTP_404_NOT_FOUND)

                # Check if expired
                if pending_registration.is_expired:
                    logger.error(f'Registration expired for order: {order_id}')
                    return Response({'error': 'Registration expired'}, status=status.HTTP_400_BAD_REQUEST)

                # Create tenant in a transaction
                with transaction.atomic():
                    # Create tenant
                    tenant = Tenant.objects.create(
                        schema_name=pending_registration.schema_name,
                        domain_url=f"{pending_registration.schema_name}.api.echodesk.ge",
                        name=pending_registration.name,
                        admin_email=pending_registration.admin_email,
                        admin_name=f"{pending_registration.admin_first_name} {pending_registration.admin_last_name}",
                        plan='paid',
                        max_users=pending_registration.package.max_users or 1000,
                        max_storage=pending_registration.package.max_storage_gb * 1024,
                        deployment_status='deploying',
                        is_active=True
                    )

                    # Update payment order with tenant
                    payment_order.tenant = tenant
                    payment_order.save()

                    # Create subscription
                    subscription = TenantSubscription.objects.create(
                        tenant=tenant,
                        package=pending_registration.package,
                        is_active=True,
                        starts_at=timezone.now(),
                        expires_at=timezone.now() + timedelta(days=30),
                        agent_count=pending_registration.agent_count,
                        current_users=1,
                        whatsapp_messages_used=0,
                        storage_used_gb=0,
                        last_billed_at=timezone.now(),
                        next_billing_date=timezone.now() + timedelta(days=30)
                    )

                    # Create admin user in tenant schema
                    with schema_context(tenant.schema_name):
                        # Create user without password first
                        admin_user = User.objects.create(
                            email=pending_registration.admin_email,
                            first_name=pending_registration.admin_first_name,
                            last_name=pending_registration.admin_last_name,
                            is_staff=True,
                            is_superuser=True,
                            is_active=True
                        )
                        # Set the already-hashed password directly
                        admin_user.password = pending_registration.admin_password
                        admin_user.save()

                    # Setup frontend access
                    deployment_service = SingleFrontendDeploymentService()
                    deployment_result = deployment_service.setup_tenant_frontend(tenant)

                    # Mark registration as processed
                    pending_registration.is_processed = True
                    pending_registration.save()

                    logger.info(f'Tenant created from registration payment: {tenant.schema_name}')

                    return Response({
                        'status': 'success',
                        'action': 'tenant_created',
                        'tenant_id': tenant.id,
                        'schema_name': tenant.schema_name
                    })

            # Regular subscription payment for existing tenant
            tenant = payment_order.tenant
            package = payment_order.package
            agent_count = payment_order.agent_count

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
                    'order_id': order_id,
                    'transaction_id': transaction_id,
                    'amount': body.get('transfer_amount'),
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

    # Handle failed payment (BOG status: 'rejected')
    elif bog_status == 'rejected':
        logger.warning(f'Payment failed: order_id={order_id}, code={response_code}')

        # Update payment order status if exists
        try:
            payment_order = PaymentOrder.objects.get(order_id=order_id)
            payment_order.status = 'failed'
            payment_order.metadata['bog_status'] = bog_status
            payment_order.metadata['response_code'] = response_code
            payment_order.save()
        except PaymentOrder.DoesNotExist:
            logger.error(f'Payment order not found for failed payment: {order_id}')

    # Handle other statuses
    else:
        logger.info(f'Webhook received with status: {bog_status}, code: {response_code}')

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
