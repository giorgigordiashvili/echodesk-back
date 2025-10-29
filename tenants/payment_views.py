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
from .email_service import email_service
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

    # BOG sends their internal order_id and our external_order_id
    bog_order_id = body.get('order_id') or body.get('id')
    external_order_id = body.get('external_order_id')
    order_status_obj = body.get('order_status', {})
    bog_status = order_status_obj.get('key', '')

    # Get response code from payment_detail
    payment_detail = body.get('payment_detail', {})
    response_code = payment_detail.get('code', '')
    transaction_id = payment_detail.get('transaction_id', '')

    logger.info(f'BOG webhook received: bog_order_id={bog_order_id}, external_order_id={external_order_id}, status={bog_status}, code={response_code}')

    # Handle successful payment (BOG status: 'completed' with response code '100')
    if bog_status == 'completed' and response_code == '100':
        try:
            # Get payment order from database using external_order_id (we store this as order_id)
            if not external_order_id:
                logger.error('Missing external_order_id in webhook payload')
                return Response({'error': 'Invalid payload'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                payment_order = PaymentOrder.objects.get(order_id=external_order_id)
            except PaymentOrder.DoesNotExist:
                logger.error(f'Payment order not found: {external_order_id}')
                return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

            # Check if already processed (idempotency - handle duplicate webhooks)
            if payment_order.status == 'paid' and payment_order.tenant is not None:
                logger.info(f'Webhook already processed for order: {external_order_id}, returning success')
                return Response({
                    'status': 'success',
                    'message': 'Payment already processed'
                }, status=status.HTTP_200_OK)

            # Update payment order status
            payment_order.status = 'paid'
            payment_order.paid_at = timezone.now()
            payment_order.save()

            # Extract card save information from webhook
            saved_card_type = payment_detail.get('saved_card_type')
            parent_order_id_from_bog = payment_detail.get('parent_order_id')

            # For trial payments, BOG returns the parent order ID that should be used for future charges
            # This is the BOG order_id (not external_order_id) that we'll use in recurring payment API calls
            card_saved_for_recurring = saved_card_type == 'subscription'

            if card_saved_for_recurring:
                logger.info(f'Card saved for recurring payments. BOG order_id: {bog_order_id}')

            # Check if this is a registration payment (no tenant yet)
            if payment_order.tenant is None:
                # This is a registration payment - create tenant from pending registration
                try:
                    pending_registration = PendingRegistration.objects.get(
                        order_id=external_order_id,
                        is_processed=False
                    )
                except PendingRegistration.DoesNotExist:
                    # Check if it was already processed (duplicate webhook)
                    processed_registration = PendingRegistration.objects.filter(
                        order_id=external_order_id,
                        is_processed=True
                    ).first()

                    if processed_registration:
                        logger.info(f'Registration already processed for order: {external_order_id}')
                        return Response({
                            'status': 'success',
                            'message': 'Registration already processed'
                        }, status=status.HTTP_200_OK)

                    logger.error(f'Pending registration not found for order: {external_order_id}')
                    return Response({'error': 'Registration not found'}, status=status.HTTP_404_NOT_FOUND)

                # Check if expired
                if pending_registration.is_expired:
                    logger.error(f'Registration expired for order: {external_order_id}')
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

                    # Check if this is a trial payment
                    is_trial = payment_order.is_trial_payment
                    trial_days = payment_order.metadata.get('trial_days', 14)

                    # Create subscription with trial information
                    if is_trial:
                        trial_ends_at = timezone.now() + timedelta(days=trial_days)

                        # Use the BOG order_id from webhook as parent_order_id for future recurring charges
                        parent_order_id_for_subscription = bog_order_id if card_saved_for_recurring else None

                        subscription = TenantSubscription.objects.create(
                            tenant=tenant,
                            package=pending_registration.package,
                            is_active=True,
                            starts_at=timezone.now(),
                            expires_at=trial_ends_at,
                            agent_count=pending_registration.agent_count,
                            current_users=1,
                            whatsapp_messages_used=0,
                            storage_used_gb=0,
                            # Trial subscription fields
                            is_trial=True,
                            trial_ends_at=trial_ends_at,
                            trial_converted=False,
                            parent_order_id=parent_order_id_for_subscription,  # Save BOG order ID for future charges
                            # Billing will happen at end of trial
                            last_billed_at=None,
                            next_billing_date=trial_ends_at
                        )
                        logger.info(f'Trial subscription created for {tenant.schema_name}, ends at {trial_ends_at}, parent_order_id: {parent_order_id_for_subscription}')
                    else:
                        # Regular paid subscription
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

                    # Create admin user in tenant schema (use savepoint to handle IntegrityError)
                    with schema_context(tenant.schema_name):
                        from django.db import IntegrityError
                        try:
                            # Use a savepoint so IntegrityError doesn't break the outer transaction
                            with transaction.atomic():
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
                                logger.info(f'Admin user created: {admin_user.email}')
                        except IntegrityError as user_error:
                            # If user already exists, retrieve it instead
                            logger.warning(f'User creation failed (may already exist): {user_error}')
                            admin_user = User.objects.filter(email=pending_registration.admin_email).first()
                            if admin_user:
                                logger.info(f'Using existing admin user: {admin_user.email}')
                            else:
                                # This shouldn't happen, but log and continue
                                logger.error(f'User lookup failed after IntegrityError: {user_error}')
                                # Don't raise - we can continue without the user being in the tenant schema

                    # Setup frontend access
                    deployment_service = SingleFrontendDeploymentService()
                    deployment_result = deployment_service.setup_tenant_frontend(tenant)

                    # Mark registration as processed
                    pending_registration.is_processed = True
                    pending_registration.save()

                    logger.info(f'Tenant created from registration payment: {tenant.schema_name}')

                    # Send welcome email to tenant admin
                    try:
                        frontend_url = tenant.frontend_url or f"https://{tenant.schema_name}.echodesk.ge"
                        email_sent = email_service.send_tenant_created_email(
                            tenant_email=pending_registration.admin_email,
                            tenant_name=pending_registration.name,
                            admin_name=f"{pending_registration.admin_first_name} {pending_registration.admin_last_name}",
                            frontend_url=frontend_url,
                            schema_name=tenant.schema_name
                        )
                        if email_sent:
                            logger.info(f'Welcome email sent to {pending_registration.admin_email}')
                        else:
                            logger.warning(f'Failed to send welcome email to {pending_registration.admin_email}')
                    except Exception as e:
                        logger.error(f'Error sending welcome email: {str(e)}')

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
                    'order_id': external_order_id,
                    'bog_order_id': bog_order_id,
                    'transaction_id': transaction_id,
                    'amount': payment_detail.get('transfer_amount'),
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
        logger.warning(f'Payment failed: external_order_id={external_order_id}, code={response_code}')

        # Update payment order status if exists
        try:
            payment_order = PaymentOrder.objects.get(order_id=external_order_id)
            payment_order.status = 'failed'
            payment_order.metadata['bog_status'] = bog_status
            payment_order.metadata['response_code'] = response_code
            payment_order.save()
        except PaymentOrder.DoesNotExist:
            logger.error(f'Payment order not found for failed payment: {external_order_id}')

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


@extend_schema(
    operation_id='get_saved_card_info',
    summary='Get Saved Card Information',
    description='Get information about the saved card for recurring payments',
    responses={
        200: OpenApiResponse(
            description='Saved card information',
            response={
                'type': 'object',
                'properties': {
                    'has_saved_card': {'type': 'boolean'},
                    'last_payment_date': {'type': 'string'},
                    'card_saved_date': {'type': 'string'},
                    'auto_renew_enabled': {'type': 'boolean'}
                }
            }
        ),
        404: OpenApiResponse(description='No subscription found')
    },
    tags=['Payments']
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_saved_card_info(request):
    """
    Get information about saved card
    """
    if not hasattr(request, 'tenant'):
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        # Find the payment order with saved card
        payment_order = PaymentOrder.objects.filter(
            tenant=request.tenant,
            card_saved=True,
            bog_order_id__isnull=False,
            status='paid'
        ).order_by('-paid_at').first()

        if payment_order:
            return Response({
                'has_saved_card': True,
                'last_payment_date': payment_order.paid_at.isoformat() if payment_order.paid_at else None,
                'card_saved_date': payment_order.paid_at.isoformat() if payment_order.paid_at else None,
                'auto_renew_enabled': True,
                'order_id': payment_order.order_id
            })
        else:
            return Response({
                'has_saved_card': False,
                'auto_renew_enabled': False
            })

    except Exception as e:
        logger.error(f'Error getting saved card info for {request.tenant.schema_name}: {e}')
        return Response(
            {'error': 'Failed to get saved card information'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    operation_id='delete_saved_card',
    summary='Delete Saved Card',
    description='Delete the saved card from BOG payment gateway',
    responses={
        200: OpenApiResponse(description='Card deleted successfully'),
        404: OpenApiResponse(description='No saved card found'),
        500: OpenApiResponse(description='Failed to delete card')
    },
    tags=['Payments']
)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_saved_card(request):
    """
    Delete the saved card from BOG
    """
    if not hasattr(request, 'tenant'):
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        # Find the payment order with saved card
        payment_order = PaymentOrder.objects.filter(
            tenant=request.tenant,
            card_saved=True,
            bog_order_id__isnull=False,
            status='paid'
        ).order_by('-paid_at').first()

        if not payment_order:
            return Response(
                {'error': 'No saved card found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Delete card from BOG
        success = bog_service.delete_saved_card(payment_order.bog_order_id)

        if success:
            # Update payment order
            payment_order.card_saved = False
            payment_order.save()

            logger.info(f'Saved card deleted for tenant {request.tenant.schema_name}')

            return Response({
                'status': 'success',
                'message': 'Saved card has been deleted. You will need to manually pay for future renewals.'
            })
        else:
            return Response(
                {'error': 'Failed to delete card from payment gateway'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    except Exception as e:
        logger.error(f'Error deleting saved card for {request.tenant.schema_name}: {e}')
        return Response(
            {'error': 'Failed to delete saved card'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    operation_id='manual_payment',
    summary='Create Manual Payment',
    description='Create a manual payment for subscription renewal (when no saved card)',
    responses={
        200: OpenApiResponse(
            description='Payment created',
            response={
                'type': 'object',
                'properties': {
                    'payment_url': {'type': 'string'},
                    'order_id': {'type': 'string'},
                    'amount': {'type': 'number'}
                }
            }
        ),
        404: OpenApiResponse(description='No active subscription found')
    },
    tags=['Payments']
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_payment(request):
    """
    Create a manual payment for subscription renewal
    Used when user doesn't have saved card or wants to pay manually
    """
    if not hasattr(request, 'tenant'):
        return Response(
            {'error': 'This endpoint is only available from tenant subdomains'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        subscription = TenantSubscription.objects.get(tenant=request.tenant, is_active=True)
        package = subscription.package

        # Calculate amount
        from .models import PricingModel
        if package.pricing_model == PricingModel.AGENT_BASED:
            amount = float(package.price_gel) * subscription.agent_count
        else:
            amount = float(package.price_gel)

        # Generate order ID
        import uuid
        external_order_id = f"MAN-{uuid.uuid4().hex[:12].upper()}"

        # Create payment
        payment_result = bog_service.create_payment(
            amount=amount,
            currency='GEL',
            external_order_id=external_order_id,
            description=f"EchoDesk Subscription Renewal - {request.tenant.name}",
            customer_email=request.tenant.admin_email,
            customer_name=request.tenant.admin_name,
            return_url_success=f"https://{request.get_host()}/settings/subscription/success",
            return_url_fail=f"https://{request.get_host()}/settings/subscription/failed",
            callback_url=f"https://api.echodesk.ge/api/payments/webhook/"
        )

        # Create payment order
        payment_order = PaymentOrder.objects.create(
            order_id=external_order_id,
            bog_order_id=payment_result.get('order_id'),
            tenant=request.tenant,
            package=package,
            amount=amount,
            currency='GEL',
            agent_count=subscription.agent_count,
            payment_url=payment_result['payment_url'],
            status='pending',
            card_saved=False,
            metadata={
                'type': 'manual_renewal',
                'subscription_id': subscription.id
            }
        )

        logger.info(f'Manual payment created for tenant {request.tenant.schema_name}: {external_order_id}')

        return Response({
            'payment_url': payment_result['payment_url'],
            'order_id': external_order_id,
            'amount': amount,
            'currency': 'GEL'
        })

    except TenantSubscription.DoesNotExist:
        return Response(
            {'error': 'No active subscription found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f'Error creating manual payment for {request.tenant.schema_name}: {e}')
        return Response(
            {'error': f'Failed to create payment: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
