"""ViewSets for the PBX management panel (Trunks, Queues, Inbound routes).

All endpoints are gated by the ``sip_calling`` subscription feature via the
``HasSubscriptionFeature`` DRF permission class. The sync layer that mirrors
these rows into Asterisk's realtime Postgres is built in a follow-up step.
"""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, permissions, viewsets

from tenants.permissions import HasSubscriptionFeature

from .models import InboundRoute, Queue, QueueMember, Trunk
from .serializers import (
    InboundRouteSerializer,
    QueueListSerializer,
    QueueMemberSerializer,
    QueueSerializer,
    TrunkListSerializer,
    TrunkSerializer,
)


class _SipCallingFeature(HasSubscriptionFeature):
    """Bind ``HasSubscriptionFeature`` to the ``sip_calling`` feature key."""

    required_feature = 'sip_calling'


@extend_schema(tags=['PBX'])
class TrunkViewSet(viewsets.ModelViewSet):
    """CRUD for tenant-owned SIP trunks.

    Trunks represent the connection to a provider (Magti, Silknet, …) and
    own the set of inbound DIDs that route through them. Gated by the
    ``sip_calling`` subscription feature.
    """

    permission_classes = [permissions.IsAuthenticated, _SipCallingFeature]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_default', 'register', 'provider']
    search_fields = ['name', 'provider', 'sip_server', 'username', 'realm']
    ordering_fields = ['name', 'provider', 'created_at', 'updated_at']
    ordering = ['-is_default', 'name']

    def get_queryset(self):
        # Tenant isolation is handled by the tenant-schemas middleware.
        return Trunk.objects.all()

    def get_serializer_class(self):
        if self.action == 'list':
            return TrunkListSerializer
        return TrunkSerializer


@extend_schema(tags=['PBX'])
class QueueViewSet(viewsets.ModelViewSet):
    """CRUD for call queues.

    A queue is backed by a ``TenantGroup`` — members with an active
    ``UserPhoneAssignment`` are materialised into ``QueueMember`` rows
    by the sync layer. Gated by the ``sip_calling`` subscription feature.
    """

    permission_classes = [permissions.IsAuthenticated, _SipCallingFeature]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'is_default', 'strategy', 'group']
    search_fields = ['name', 'slug', 'group__name']
    ordering_fields = ['name', 'slug', 'created_at', 'updated_at']
    ordering = ['-is_default', 'name']

    def get_queryset(self):
        return Queue.objects.select_related('group').prefetch_related('members').all()

    def get_serializer_class(self):
        if self.action == 'list':
            return QueueListSerializer
        return QueueSerializer


@extend_schema(tags=['PBX'])
class QueueMemberViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only view over ``QueueMember`` rows.

    Rows are materialised by the sync layer — there is no create/update/delete.
    Filter by ``?queue=N`` to list an individual queue's agents.
    """

    serializer_class = QueueMemberSerializer
    permission_classes = [permissions.IsAuthenticated, _SipCallingFeature]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['queue', 'is_active', 'paused']
    search_fields = [
        'queue__name', 'queue__slug',
        'user_phone_assignment__extension',
        'user_phone_assignment__phone_number',
        'user_phone_assignment__user__email',
    ]
    ordering_fields = ['queue', 'penalty', 'synced_at']
    ordering = ['queue', 'penalty']

    def get_queryset(self):
        return QueueMember.objects.select_related(
            'queue', 'user_phone_assignment', 'user_phone_assignment__user',
        ).all()


@extend_schema(tags=['PBX'])
class InboundRouteViewSet(viewsets.ModelViewSet):
    """CRUD for DID-to-destination routing rules."""

    serializer_class = InboundRouteSerializer
    permission_classes = [permissions.IsAuthenticated, _SipCallingFeature]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['destination_type', 'is_active', 'trunk', 'destination_queue']
    search_fields = ['did', 'ivr_custom_context', 'trunk__name', 'destination_queue__slug']
    ordering_fields = ['priority', 'did', 'created_at', 'updated_at']
    ordering = ['priority', 'did']

    def get_queryset(self):
        return InboundRoute.objects.select_related(
            'trunk', 'destination_queue', 'destination_extension', 'working_hours_override',
        ).all()
