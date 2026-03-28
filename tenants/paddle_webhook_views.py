"""
Paddle Billing webhook handler.

Handles Paddle events for subscription lifecycle and payments.
Docs: https://developer.paddle.com/webhooks/overview
"""
import json
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import (
    Tenant, TenantSubscription, PaymentOrder, PendingRegistration,
    Invoice, PaymentAttempt, SubscriptionEvent,
)
from .payment_providers.paddle import PaddlePaymentProvider
from .email_service import email_service
from .telegram_notifications import (
    notify_subscription_created, notify_payment_success, notify_payment_failed,
)

logger = logging.getLogger(__name__)

# Singleton Paddle provider for webhook verification
_paddle_provider = None


def _get_paddle_provider():
    global _paddle_provider
    if _paddle_provider is None:
        _paddle_provider = PaddlePaymentProvider()
    return _paddle_provider


def _get_next_billing_date():
    """Calculate next billing date (mirrors payment_views.get_next_billing_date)."""
    if getattr(settings, 'TEST_BILLING_INTERVAL', False):
        return timezone.now() + timedelta(minutes=2)
    return timezone.now() + timedelta(days=30)


def _generate_invoice(payment_order, tenant, agent_count, description=None):
    """Generate an invoice for a successful payment."""
    try:
        if hasattr(payment_order, 'invoice'):
            return payment_order.invoice

        if payment_order.amount <= 0:
            return None

        if not description:
            description = f"Subscription payment for {agent_count} agents"

        invoice = Invoice.objects.create(
            tenant=tenant,
            payment_order=payment_order,
            amount=payment_order.amount,
            currency=payment_order.currency,
            description=description,
            agent_count=agent_count,
            paid_date=payment_order.paid_at or timezone.now(),
            metadata={
                'order_id': payment_order.order_id,
                'provider': 'paddle',
                'provider_order_id': payment_order.provider_order_id,
            },
        )
        logger.info(f'Invoice {invoice.invoice_number} generated for Paddle payment {payment_order.order_id}')
        return invoice
    except Exception as e:
        logger.error(f'Error generating invoice for Paddle payment {payment_order.order_id}: {e}')
        return None


def _trigger_tenant_processing(schema_name):
    """Dispatch async tenant setup via Celery."""
    try:
        from tenants.tasks import process_pending_tenant
        process_pending_tenant.delay(schema_name)
        logger.info(f'Dispatched process_pending_tenant task for: {schema_name}')
    except Exception as e:
        logger.error(f'Failed to dispatch tenant processing for {schema_name}: {e}')


# ── Main webhook view ────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([AllowAny])
def paddle_webhook(request):
    """
    Handle Paddle Billing webhook events.

    Paddle sends events as JSON with a Paddle-Signature header for HMAC verification.
    """
    provider = _get_paddle_provider()

    # Verify signature
    if not provider.verify_webhook(dict(request.headers), request.body):
        logger.warning('Paddle webhook signature verification failed')
        return Response({'error': 'Invalid signature'}, status=status.HTTP_400_BAD_REQUEST)

    data = request.data
    event_type = data.get('event_type', '')
    event_data = data.get('data', {})

    logger.info(f'Paddle webhook received: event_type={event_type}, id={event_data.get("id", "")}')

    handler = _EVENT_HANDLERS.get(event_type)
    if handler:
        try:
            return handler(event_data)
        except Exception as e:
            logger.error(f'Paddle webhook handler error for {event_type}: {e}', exc_info=True)
            return Response({'error': 'Internal error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        logger.info(f'Unhandled Paddle event type: {event_type}')
        return Response({'status': 'ignored'}, status=status.HTTP_200_OK)


# ── Event handlers ───────────────────────────────────────────────

def _handle_transaction_completed(event_data):
    """
    Handle transaction.completed — payment succeeded.

    This covers:
    - Registration payments (PendingRegistration)
    - Subscription renewals
    - One-time payments
    """
    transaction_id = event_data.get('id', '')
    custom_data = event_data.get('custom_data', {})
    external_order_id = custom_data.get('external_order_id', '')

    if not external_order_id:
        logger.warning(f'Paddle transaction {transaction_id} missing external_order_id in custom_data')
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)

    try:
        payment_order = PaymentOrder.objects.get(order_id=external_order_id)
    except PaymentOrder.DoesNotExist:
        logger.error(f'PaymentOrder not found for external_order_id={external_order_id}')
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

    # Idempotency check
    if payment_order.status == 'paid' and payment_order.tenant is not None:
        logger.info(f'Paddle webhook already processed for order: {external_order_id}')
        return Response({'status': 'already_processed'}, status=status.HTTP_200_OK)

    # Update payment order
    payment_order.status = 'paid'
    payment_order.paid_at = timezone.now()
    payment_order.provider_order_id = transaction_id
    payment_order.save()

    # Extract amount from Paddle data
    details = event_data.get('details', {})
    totals = details.get('totals', {})
    amount_str = totals.get('total', '0')
    # Paddle amounts are in lowest denomination (cents)
    amount = int(amount_str) / 100 if amount_str else float(payment_order.amount)

    # Registration payment (no tenant yet)
    if payment_order.tenant is None:
        return _process_registration_payment(payment_order, event_data)

    # Existing tenant — renewal or one-time
    tenant = payment_order.tenant
    subscription = getattr(tenant, 'subscription', None)

    if subscription:
        # Create payment attempt record
        PaymentAttempt.objects.create(
            payment_order=payment_order,
            subscription=subscription,
            tenant=tenant,
            attempt_number=1,
            status='success',
            bog_order_id=transaction_id,
            amount=payment_order.amount,
            attempted_at=timezone.now(),
            completed_at=timezone.now(),
            bog_response=event_data,
        )

        # Update subscription billing dates
        subscription.last_billed_at = timezone.now()
        subscription.next_billing_date = _get_next_billing_date()
        subscription.mark_payment_succeeded()

        # Log event
        SubscriptionEvent.objects.create(
            subscription=subscription,
            tenant=tenant,
            event_type='payment_success',
            payment_order=payment_order,
            description=f'Paddle payment succeeded: {transaction_id}',
            metadata={'paddle_transaction_id': transaction_id},
        )

        # Generate invoice
        _generate_invoice(payment_order, tenant, subscription.agent_count)

        try:
            notify_payment_success(subscription, payment_order)
        except Exception:
            pass

    return Response({'status': 'success'}, status=status.HTTP_200_OK)


def _process_registration_payment(payment_order, event_data):
    """Handle a registration payment — create tenant from PendingRegistration."""
    external_order_id = payment_order.order_id
    transaction_id = event_data.get('id', '')
    custom_data = event_data.get('custom_data', {})

    try:
        pending = PendingRegistration.objects.get(
            order_id=external_order_id,
            is_processed=False,
        )
    except PendingRegistration.DoesNotExist:
        if PendingRegistration.objects.filter(order_id=external_order_id, is_processed=True).exists():
            return Response({'status': 'already_processed'}, status=status.HTTP_200_OK)
        logger.error(f'PendingRegistration not found for order: {external_order_id}')
        return Response({'error': 'Registration not found'}, status=status.HTTP_404_NOT_FOUND)

    if pending.is_expired:
        logger.error(f'Registration expired for order: {external_order_id}')
        return Response({'error': 'Registration expired'}, status=status.HTTP_400_BAD_REQUEST)

    # Extract Paddle customer ID if available
    paddle_customer_id = event_data.get('customer_id', '')

    with transaction.atomic():
        max_users = pending.agent_count or 1000
        max_storage = 100 * 1024  # 100 GB default

        tenant = Tenant.objects.create(
            schema_name=pending.schema_name,
            domain_url=f"{pending.schema_name}.api.echodesk.ge",
            name=pending.name,
            admin_email=pending.admin_email,
            admin_name=f"{pending.admin_first_name} {pending.admin_last_name}",
            plan='paid',
            max_users=max_users,
            max_storage=max_storage,
            deployment_status='deploying',
            is_active=True,
            payment_provider='paddle',
            paddle_customer_id=paddle_customer_id,
        )

        payment_order.tenant = tenant
        payment_order.save()

        # Create subscription
        next_billing = _get_next_billing_date()
        subscription = TenantSubscription.objects.create(
            tenant=tenant,
            is_active=True,
            starts_at=timezone.now(),
            expires_at=next_billing,
            agent_count=pending.agent_count,
            current_users=1,
            whatsapp_messages_used=0,
            storage_used_gb=0,
            is_trial=False,
            last_billed_at=timezone.now(),
            next_billing_date=next_billing,
            payment_status='current',
            subscription_type='paid',
        )

        # Set selected features
        if pending.selected_features.exists():
            subscription.selected_features.set(pending.selected_features.all())

        # Mark registration as processed
        pending.is_processed = True
        pending.save()

        # Create payment attempt
        PaymentAttempt.objects.create(
            payment_order=payment_order,
            subscription=subscription,
            tenant=tenant,
            attempt_number=1,
            status='success',
            bog_order_id=transaction_id,
            amount=payment_order.amount,
            attempted_at=timezone.now(),
            completed_at=timezone.now(),
            bog_response=event_data,
        )

        # Log events
        SubscriptionEvent.objects.create(
            subscription=subscription,
            tenant=tenant,
            event_type='created',
            payment_order=payment_order,
            description=f'Subscription created via Paddle payment',
            metadata={
                'paddle_transaction_id': transaction_id,
                'paddle_customer_id': paddle_customer_id,
            },
        )
        SubscriptionEvent.objects.create(
            subscription=subscription,
            tenant=tenant,
            event_type='activated',
            payment_order=payment_order,
            description='Subscription activated after Paddle payment',
        )

        # Generate invoice
        _generate_invoice(payment_order, tenant, pending.agent_count)

        # Trigger async tenant setup (schema creation, admin user, etc.)
        _trigger_tenant_processing(pending.schema_name)

        logger.info(f'Paddle registration completed for {pending.schema_name}: tenant_id={tenant.id}')

        try:
            notify_subscription_created(subscription, payment_order)
        except Exception:
            pass

    return Response({'status': 'success'}, status=status.HTTP_200_OK)


def _handle_transaction_payment_failed(event_data):
    """Handle transaction.payment_failed — payment failed."""
    transaction_id = event_data.get('id', '')
    custom_data = event_data.get('custom_data', {})
    external_order_id = custom_data.get('external_order_id', '')

    if not external_order_id:
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)

    try:
        payment_order = PaymentOrder.objects.get(order_id=external_order_id)
    except PaymentOrder.DoesNotExist:
        return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

    payment_order.status = 'failed'
    payment_order.save()

    tenant = payment_order.tenant
    if tenant:
        subscription = getattr(tenant, 'subscription', None)
        if subscription:
            PaymentAttempt.objects.create(
                payment_order=payment_order,
                subscription=subscription,
                tenant=tenant,
                attempt_number=1,
                status='failed',
                bog_order_id=transaction_id,
                amount=payment_order.amount,
                attempted_at=timezone.now(),
                completed_at=timezone.now(),
                failed_reason='Paddle payment failed',
                bog_response=event_data,
            )

            subscription.mark_payment_failed()

            SubscriptionEvent.objects.create(
                subscription=subscription,
                tenant=tenant,
                event_type='payment_failed',
                payment_order=payment_order,
                description=f'Paddle payment failed: {transaction_id}',
                metadata={'paddle_transaction_id': transaction_id},
            )

            try:
                notify_payment_failed(subscription, payment_order)
            except Exception:
                pass

    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


def _handle_subscription_created(event_data):
    """
    Handle subscription.created — store Paddle subscription ID.
    Paddle creates the subscription after the first transaction completes.
    """
    subscription_id = event_data.get('id', '')
    custom_data = event_data.get('custom_data', {})
    paddle_customer_id = event_data.get('customer_id', '')

    # Find tenant by Paddle customer ID
    tenant = None
    if paddle_customer_id:
        tenant = Tenant.objects.filter(paddle_customer_id=paddle_customer_id).first()

    if not tenant:
        # Try to find via custom_data
        external_order_id = custom_data.get('external_order_id', '')
        if external_order_id:
            try:
                po = PaymentOrder.objects.get(order_id=external_order_id)
                tenant = po.tenant
            except PaymentOrder.DoesNotExist:
                pass

    if tenant:
        subscription = getattr(tenant, 'subscription', None)
        if subscription:
            subscription.provider_subscription_id = subscription_id
            subscription.save(update_fields=['provider_subscription_id'])
            logger.info(f'Stored Paddle subscription_id={subscription_id} for tenant {tenant.schema_name}')

            SubscriptionEvent.objects.create(
                subscription=subscription,
                tenant=tenant,
                event_type='created',
                description=f'Paddle subscription created: {subscription_id}',
                metadata={'paddle_subscription_id': subscription_id},
            )
    else:
        logger.warning(f'Could not find tenant for Paddle subscription.created: {subscription_id}')

    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


def _handle_subscription_updated(event_data):
    """
    Handle subscription.updated — sync changes (pause, resume, item changes).
    """
    subscription_id = event_data.get('id', '')
    paddle_status = event_data.get('status', '')

    # Find our subscription
    try:
        sub = TenantSubscription.objects.get(provider_subscription_id=subscription_id)
    except TenantSubscription.DoesNotExist:
        logger.warning(f'TenantSubscription not found for Paddle subscription: {subscription_id}')
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)

    # Handle status changes
    if paddle_status == 'paused':
        sub.is_active = False
        sub.save(update_fields=['is_active'])
        SubscriptionEvent.objects.create(
            subscription=sub,
            tenant=sub.tenant,
            event_type='suspended',
            description=f'Subscription paused via Paddle',
            metadata={'paddle_status': paddle_status},
        )
    elif paddle_status == 'active':
        if not sub.is_active:
            sub.is_active = True
            sub.save(update_fields=['is_active'])
            SubscriptionEvent.objects.create(
                subscription=sub,
                tenant=sub.tenant,
                event_type='reactivated',
                description='Subscription resumed via Paddle',
            )

    # Sync next billing date if provided
    next_billed_at = event_data.get('next_billed_at')
    if next_billed_at:
        from django.utils.dateparse import parse_datetime
        parsed = parse_datetime(next_billed_at)
        if parsed:
            sub.next_billing_date = parsed
            sub.save(update_fields=['next_billing_date'])

    logger.info(f'Paddle subscription.updated processed: {subscription_id}, status={paddle_status}')
    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


def _handle_subscription_canceled(event_data):
    """Handle subscription.canceled — deactivate subscription."""
    subscription_id = event_data.get('id', '')

    try:
        sub = TenantSubscription.objects.get(provider_subscription_id=subscription_id)
    except TenantSubscription.DoesNotExist:
        logger.warning(f'TenantSubscription not found for cancelled Paddle subscription: {subscription_id}')
        return Response({'status': 'ok'}, status=status.HTTP_200_OK)

    sub.is_active = False
    sub.save(update_fields=['is_active'])

    SubscriptionEvent.objects.create(
        subscription=sub,
        tenant=sub.tenant,
        event_type='cancelled',
        description='Subscription cancelled via Paddle',
        metadata={'paddle_subscription_id': subscription_id},
    )

    logger.info(f'Paddle subscription cancelled: {subscription_id} for tenant {sub.tenant.schema_name}')
    return Response({'status': 'ok'}, status=status.HTTP_200_OK)


# ── Event routing table ──────────────────────────────────────────

_EVENT_HANDLERS = {
    'transaction.completed': _handle_transaction_completed,
    'transaction.payment_failed': _handle_transaction_payment_failed,
    'subscription.created': _handle_subscription_created,
    'subscription.updated': _handle_subscription_updated,
    'subscription.canceled': _handle_subscription_canceled,
}
