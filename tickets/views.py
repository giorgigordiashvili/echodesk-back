from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q
from .models import Ticket, Tag, TicketComment
from .serializers import (
    TicketSerializer, TicketListSerializer, TagSerializer, 
    TicketCommentSerializer
)


class TicketPermission(permissions.BasePermission):
    """
    Custom permission for tickets:
    - Anyone authenticated can create tickets
    - Only staff can assign tickets or close them
    - Users can view their own tickets or tickets assigned to them
    """
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Staff users have full access
        if request.user.is_staff:
            return True
        
        # Users can view tickets they created or are assigned to
        if request.method in permissions.SAFE_METHODS:
            return (obj.created_by == request.user or 
                   obj.assigned_to == request.user)
        
        # Only staff can assign tickets or change status to 'closed'
        if request.method in ['PUT', 'PATCH']:
            # Check if trying to assign ticket or close it
            if 'assigned_to_id' in request.data or request.data.get('status') == 'closed':
                return request.user.is_staff
            # Users can edit their own tickets (but not assign or close)
            return obj.created_by == request.user
        
        # Only staff can delete tickets
        if request.method == 'DELETE':
            return request.user.is_staff
        
        return False


class TicketViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tickets with filtering and permissions.
    """
    queryset = Ticket.objects.all().select_related(
        'created_by', 'assigned_to'
    ).prefetch_related('tags', 'comments')
    serializer_class = TicketSerializer
    permission_classes = [TicketPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'priority', 'assigned_to', 'created_by', 'tags']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'priority', 'status']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Use list serializer for list action."""
        if self.action == 'list':
            return TicketListSerializer
        return TicketSerializer

    def get_queryset(self):
        """
        Filter queryset based on user permissions and query parameters.
        """
        queryset = super().get_queryset()
        
        # Non-staff users can only see their tickets
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(created_by=self.request.user) | 
                Q(assigned_to=self.request.user)
            )
        
        # Additional filtering by query parameters
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        priority_filter = self.request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        
        assigned_to_filter = self.request.query_params.get('assigned_to')
        if assigned_to_filter:
            queryset = queryset.filter(assigned_to_id=assigned_to_filter)
        
        created_by_filter = self.request.query_params.get('created_by')
        if created_by_filter:
            queryset = queryset.filter(created_by_id=created_by_filter)
        
        return queryset

    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """Add a comment to a ticket."""
        ticket = self.get_object()
        serializer = TicketCommentSerializer(
            data=request.data, 
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save(ticket=ticket, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['get'])
    def comments(self, request, pk=None):
        """Get all comments for a ticket."""
        ticket = self.get_object()
        comments = ticket.comments.all()
        serializer = TicketCommentSerializer(comments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_tickets(self, request):
        """Get tickets created by the current user."""
        queryset = self.queryset.filter(created_by=request.user)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TicketListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = TicketListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def assigned_to_me(self, request):
        """Get tickets assigned to the current user."""
        queryset = self.queryset.filter(assigned_to=request.user)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = TicketListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = TicketListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def assign(self, request, pk=None):
        """Assign a ticket to a user (staff only)."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Only staff can assign tickets.'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        ticket = self.get_object()
        assigned_to_id = request.data.get('assigned_to_id')
        
        if assigned_to_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                assigned_user = User.objects.get(id=assigned_to_id)
                ticket.assigned_to = assigned_user
                ticket.save()
                serializer = self.get_serializer(ticket)
                return Response(serializer.data)
            except User.DoesNotExist:
                return Response(
                    {'error': 'User not found.'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            ticket.assigned_to = None
            ticket.save()
            serializer = self.get_serializer(ticket)
            return Response(serializer.data)


class TagViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing tags.
    """
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name']
    ordering = ['name']

    def get_permissions(self):
        """
        Only staff can create, update, or delete tags.
        Anyone authenticated can view tags.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]


class TicketCommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ticket comments.
    """
    serializer_class = TicketCommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering = ['created_at']

    def get_queryset(self):
        """Get comments for tickets the user has access to."""
        if self.request.user.is_staff:
            return TicketComment.objects.all().select_related('user', 'ticket')
        
        # Non-staff users can only see comments on their tickets
        return TicketComment.objects.filter(
            Q(ticket__created_by=self.request.user) | 
            Q(ticket__assigned_to=self.request.user)
        ).select_related('user', 'ticket')

    def perform_create(self, serializer):
        """Set the user when creating a comment."""
        serializer.save(user=self.request.user)
