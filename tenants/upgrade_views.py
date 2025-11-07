"""
Package Upgrade Views for Tenant Subscriptions

Handles immediate and scheduled package upgrades with BOG subscription payments.
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
import uuid
import logging

from .models import (
    TenantSubscription, Package, PaymentOrder, SavedCard
)
from tenants.bog_payment import bog_service

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def upgrade_preview(request):
    """
    Preview package upgrade details (pricing, features, timing options)

    Query params:
        - package_id: ID of package to upgrade to
        - upgrade_type: 'immediate' or 'scheduled' (optional, for cost preview)
    """
    try:
        # Get current subscription
        subscription = TenantSubscription.objects.select_related('package').get(
            tenant=request.tenant,
            is_active=True
        )
    except TenantSubscription.DoesNotExist:
        return Response(
            {'error': 'No active subscription found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Get target package
    package_id = request.query_params.get('package_id')
    if not package_id:
        return Response(
            {'error': 'package_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        new_package = Package.objects.get(id=package_id, is_active=True, is_custom=False)
    except Package.DoesNotExist:
        return Response(
            {'error': 'Package not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Check if upgrading to same package
    if subscription.package.id == new_package.id:
        return Response(
            {'error': 'Cannot upgrade to the same package'},
            status=status.HTTP_400_BAD_REQUEST
        )

    current_package = subscription.package
    current_price = float(current_package.price_gel)
    new_price = float(new_package.price_gel)
    price_difference = new_price - current_price

    # Calculate days remaining in current billing period
    days_remaining = 0
    forfeited_amount = 0
    if subscription.next_billing_date:
        days_remaining = (subscription.next_billing_date - timezone.now()).days
        if days_remaining > 0:
            # Calculate prorated forfeited amount (informational only, no refunds)
            days_in_period = 30  # Approximate
            forfeited_amount = (current_price / days_in_period) * days_remaining

    return Response({
        'current_package': {
            'id': current_package.id,
            'name': current_package.display_name,
            'price': current_price,
        },
        'new_package': {
            'id': new_package.id,
            'name': new_package.display_name,
            'price': new_price,
        },
        'pricing': {
            'current_monthly_cost': current_price,
            'new_monthly_cost': new_price,
            'price_difference': price_difference,
            'is_upgrade': price_difference > 0,
            'is_downgrade': price_difference < 0,
        },
        'timing': {
            'days_remaining_in_period': max(0, days_remaining),
            'next_billing_date': subscription.next_billing_date.isoformat() if subscription.next_billing_date else None,
        },
        'immediate_upgrade': {
            'available': True,
            'charge_now': new_price,
            'forfeited_amount': round(forfeited_amount, 2),
            'note': 'Current subscription will be cancelled immediately. Remaining time will be forfeited (no refund).'
        },
        'scheduled_upgrade': {
            'available': True,
            'effective_date': subscription.next_billing_date.isoformat() if subscription.next_billing_date else None,
            'charge_at_next_billing': new_price,
            'note': 'Upgrade will take effect at next billing cycle. You keep current package until then.'
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upgrade_immediate(request):
    """
    Immediately upgrade to a new package

    Process:
    1. Cancel current subscription
    2. Create payment for new package with subscription card saving
    3. User completes payment (may require 3D Secure)
    4. Webhook activates new subscription

    POST body:
        - package_id: ID of package to upgrade to
    """
    package_id = request.data.get('package_id')
    if not package_id:
        return Response(
            {'error': 'package_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        with transaction.atomic():
            # Get current subscription (lock for update)
            try:
                subscription = TenantSubscription.objects.select_for_update().select_related('package').get(
                    tenant=request.tenant,
                    is_active=True
                )
            except TenantSubscription.DoesNotExist:
                return Response(
                    {'error': 'No active subscription found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get target package
            try:
                new_package = Package.objects.get(id=package_id, is_active=True, is_custom=False)
            except Package.DoesNotExist:
                return Response(
                    {'error': 'Package not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Validate upgrade
            if subscription.package.id == new_package.id:
                return Response(
                    {'error': 'Cannot upgrade to the same package'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            current_package = subscription.package
            new_amount = float(new_package.price_gel)

            # Generate unique order ID
            order_id = f"UPG-{uuid.uuid4().hex[:12].upper()}"

            # Create payment order
            payment_order = PaymentOrder.objects.create(
                order_id=order_id,
                tenant=request.tenant,
                package=new_package,
                previous_package=current_package,
                amount=new_amount,
                currency='GEL',
                agent_count=1,  # Deprecated field
                status='pending',
                is_immediate_upgrade=True,
                card_saved=False,  # Will be set after payment
                metadata={
                    'type': 'immediate_upgrade',
                    'previous_package_id': current_package.id,
                    'previous_package_name': current_package.name,
                    'subscription_id': subscription.id
                }
            )

            # Create BOG payment with subscription card saving
            payment_result = bog_service.create_payment(
                amount=new_amount,
                currency='GEL',
                description=f"EchoDesk Package Upgrade - {new_package.display_name}",
                customer_email=request.tenant.admin_email if hasattr(request.tenant, 'admin_email') else '',
                customer_name=request.tenant.name,
                return_url_success=f"https://{request.tenant.schema_name}.echodesk.ge/settings/subscription/success",
                return_url_fail=f"https://{request.tenant.schema_name}.echodesk.ge/settings/subscription/failed",
                callback_url=f"https://api.echodesk.ge/api/payments/webhook/",
                external_order_id=order_id,
                metadata={
                    'tenant_id': request.tenant.id,
                    'tenant_schema': request.tenant.schema_name,
                    'upgrade_type': 'immediate'
                }
            )

            # Enable subscription card saving
            bog_order_id = payment_result['order_id']
            card_saving_enabled = bog_service.enable_subscription_card_saving(bog_order_id)

            if not card_saving_enabled:
                logger.warning(f'Failed to enable subscription card saving for upgrade: {bog_order_id}')

            # Update payment order with BOG details
            payment_order.bog_order_id = bog_order_id
            payment_order.payment_url = payment_result['payment_url']
            payment_order.card_saved = card_saving_enabled
            payment_order.save()

            # Mark subscription as upgrading (will be updated by webhook)
            subscription.subscription_type = 'upgrading'
            subscription.save()

            logger.info(f'Immediate upgrade initiated for {request.tenant.schema_name}: {current_package.name} -> {new_package.name}')

            return Response({
                'message': 'Upgrade payment created',
                'order_id': order_id,
                'payment_url': payment_result['payment_url'],
                'amount': new_amount,
                'currency': 'GEL',
                'package': {
                    'id': new_package.id,
                    'name': new_package.display_name,
                    'price': new_amount
                },
                'note': 'Please complete the payment to activate your new package. Your current subscription will be cancelled upon successful payment.'
            }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f'Error initiating immediate upgrade: {e}')
        return Response(
            {'error': 'Failed to initiate upgrade', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upgrade_scheduled(request):
    """
    Schedule package upgrade for next billing cycle

    No immediate payment required. Upgrade takes effect at next billing date.

    POST body:
        - package_id: ID of package to upgrade to
        - effective_date: Optional custom date (defaults to next_billing_date)
    """
    package_id = request.data.get('package_id')
    if not package_id:
        return Response(
            {'error': 'package_id is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        with transaction.atomic():
            # Get current subscription
            try:
                subscription = TenantSubscription.objects.select_for_update().select_related('package').get(
                    tenant=request.tenant,
                    is_active=True
                )
            except TenantSubscription.DoesNotExist:
                return Response(
                    {'error': 'No active subscription found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Get target package
            try:
                new_package = Package.objects.get(id=package_id, is_active=True, is_custom=False)
            except Package.DoesNotExist:
                return Response(
                    {'error': 'Package not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Validate upgrade
            if subscription.package.id == new_package.id:
                return Response(
                    {'error': 'Cannot upgrade to the same package'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if subscription.pending_package:
                return Response(
                    {'error': 'An upgrade is already scheduled. Cancel it first to schedule a different upgrade.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Set effective date (default to next billing date)
            effective_date = request.data.get('effective_date')
            if effective_date:
                from datetime import datetime
                effective_date = datetime.fromisoformat(effective_date.replace('Z', '+00:00'))
            else:
                effective_date = subscription.next_billing_date

            if not effective_date:
                return Response(
                    {'error': 'No next_billing_date set. Cannot schedule upgrade.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Schedule the upgrade
            subscription.pending_package = new_package
            subscription.upgrade_scheduled_for = effective_date
            subscription.subscription_type = 'paid'  # Keep as paid until upgrade happens
            subscription.save()

            logger.info(f'Scheduled upgrade for {request.tenant.schema_name}: {subscription.package.name} -> {new_package.name} on {effective_date}')

            return Response({
                'message': 'Upgrade scheduled successfully',
                'current_package': {
                    'id': subscription.package.id,
                    'name': subscription.package.display_name,
                },
                'scheduled_package': {
                    'id': new_package.id,
                    'name': new_package.display_name,
                    'price': float(new_package.price_gel)
                },
                'effective_date': effective_date.isoformat(),
                'note': 'Your current package will remain active until the scheduled date. The new package will be charged automatically at the next billing cycle.'
            }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f'Error scheduling upgrade: {e}')
        return Response(
            {'error': 'Failed to schedule upgrade', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_scheduled_upgrade(request):
    """
    Cancel a scheduled package upgrade

    Returns subscription to normal state without pending upgrade.
    """
    try:
        with transaction.atomic():
            # Get current subscription
            try:
                subscription = TenantSubscription.objects.select_for_update().get(
                    tenant=request.tenant,
                    is_active=True
                )
            except TenantSubscription.DoesNotExist:
                return Response(
                    {'error': 'No active subscription found'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # Check if there's a scheduled upgrade
            if not subscription.pending_package:
                return Response(
                    {'error': 'No scheduled upgrade to cancel'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            pending_package_name = subscription.pending_package.display_name

            # Cancel the scheduled upgrade
            subscription.pending_package = None
            subscription.upgrade_scheduled_for = None
            subscription.save()

            logger.info(f'Cancelled scheduled upgrade for {request.tenant.schema_name}: {pending_package_name}')

            return Response({
                'message': 'Scheduled upgrade cancelled successfully',
                'current_package': {
                    'id': subscription.package.id,
                    'name': subscription.package.display_name,
                },
                'note': 'You will continue with your current package at the next billing cycle.'
            }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f'Error cancelling scheduled upgrade: {e}')
        return Response(
            {'error': 'Failed to cancel scheduled upgrade', 'details': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
