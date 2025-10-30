from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import PushSubscription, NotificationLog
from .serializers import (
    PushSubscriptionSerializer,
    SubscribeSerializer,
    UnsubscribeSerializer,
    NotificationLogSerializer
)
from .utils import get_vapid_keys, send_notification_to_user


class NotificationViewSet(viewsets.ViewSet):
    """ViewSet for managing push notifications."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='vapid-public-key')
    def vapid_public_key(self, request):
        """Get VAPID public key for client-side subscription."""
        vapid_keys = get_vapid_keys()
        return Response({
            'public_key': vapid_keys['public_key']
        })

    @action(detail=False, methods=['post'])
    def subscribe(self, request):
        """Subscribe user to push notifications."""
        serializer = SubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        subscription_data = serializer.validated_data['subscription']

        # Extract subscription details
        endpoint = subscription_data['endpoint']
        p256dh = subscription_data['keys']['p256dh']
        auth = subscription_data['keys']['auth']

        # Get or create subscription
        subscription, created = PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                'user': request.user,
                'p256dh': p256dh,
                'auth': auth,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                'is_active': True
            }
        )

        return Response({
            'message': 'Subscribed successfully',
            'subscription_id': subscription.id,
            'created': created
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def unsubscribe(self, request):
        """Unsubscribe user from push notifications."""
        serializer = UnsubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        endpoint = serializer.validated_data['endpoint']

        # Find and deactivate subscription
        try:
            subscription = PushSubscription.objects.get(
                user=request.user,
                endpoint=endpoint
            )
            subscription.is_active = False
            subscription.save()

            return Response({
                'message': 'Unsubscribed successfully'
            })
        except PushSubscription.DoesNotExist:
            return Response({
                'error': 'Subscription not found'
            }, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def test(self, request):
        """Send a test notification to the user."""
        sent_count = send_notification_to_user(
            user=request.user,
            title='Test Notification',
            body='This is a test notification from EchoDesk!',
            data={'test': True},
            tag='test-notification'
        )

        if sent_count > 0:
            return Response({
                'message': f'Test notification sent to {sent_count} device(s)'
            })
        else:
            return Response({
                'error': 'No active subscriptions found or notification failed'
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def subscriptions(self, request):
        """Get user's active subscriptions."""
        subscriptions = PushSubscription.objects.filter(
            user=request.user,
            is_active=True
        )
        serializer = PushSubscriptionSerializer(subscriptions, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def logs(self, request):
        """Get user's notification logs."""
        logs = NotificationLog.objects.filter(user=request.user)[:50]
        serializer = NotificationLogSerializer(logs, many=True)
        return Response(serializer.data)
