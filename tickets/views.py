from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, F, Max
from django.db import transaction
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes
from .models import Ticket, Tag, TicketComment, TicketColumn
from .serializers import (
    TicketSerializer, TicketListSerializer, TagSerializer, 
    TicketCommentSerializer, TicketColumnSerializer, 
    TicketColumnCreateSerializer, TicketColumnUpdateSerializer,
    KanbanBoardSerializer
)


class TicketColumnViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ticket columns (Kanban board columns).
    """
    queryset = TicketColumn.objects.all()
    serializer_class = TicketColumnSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering = ['position', 'created_at']

    def get_serializer_class(self):
        """Use different serializers for different actions."""
        if self.action == 'create':
            return TicketColumnCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TicketColumnUpdateSerializer
        return TicketColumnSerializer

    def get_permissions(self):
        """
        Only staff can create, update, or delete columns.
        Anyone authenticated can view columns.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def reorder(self, request, pk=None):
        """Reorder columns."""
        column = self.get_object()
        new_position = request.data.get('position')
        
        if new_position is None:
            return Response(
                {'error': 'Position is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_position = int(new_position)
        except ValueError:
            return Response(
                {'error': 'Position must be a number'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Update positions of other columns
            if new_position > column.position:
                # Moving right - decrease position of columns in between
                TicketColumn.objects.filter(
                    position__gt=column.position,
                    position__lte=new_position
                ).update(position=F('position') - 1)
            else:
                # Moving left - increase position of columns in between
                TicketColumn.objects.filter(
                    position__gte=new_position,
                    position__lt=column.position
                ).update(position=F('position') + 1)
            
            # Update the column's position
            column.position = new_position
            column.save()
        
        return Response({'message': 'Column reordered successfully'})

    @extend_schema(
        operation_id='kanban_board',
        summary='Get Kanban Board',
        description='Get all columns with their tickets organized for Kanban board display.',
        responses={
            200: KanbanBoardSerializer,
        },
        tags=['Kanban Board']
    )
    @action(detail=False, methods=['get'])
    def kanban_board(self, request):
        """Get all columns with their tickets for Kanban board view."""
        columns = self.get_queryset()
        board_data = {
            'columns': columns
        }
        serializer = KanbanBoardSerializer(board_data, context={'request': request})
        return Response(serializer.data)


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
    filterset_fields = ['status', 'priority', 'assigned_to', 'created_by', 'tags', 'column']
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

    @extend_schema(
        operation_id='move_ticket_to_column',
        summary='Move Ticket to Column',
        description='Move a ticket to a different column in the Kanban board and optionally set its position.',
        request={
            'type': 'object',
            'properties': {
                'column_id': {'type': 'integer'},
                'position_in_column': {'type': 'integer', 'nullable': True}
            },
            'required': ['column_id']
        },
        responses={
            200: TicketSerializer,
            400: OpenApiResponse(description='Invalid column or missing column_id'),
        },
        tags=['Kanban Board']
    )
    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def move_to_column(self, request, pk=None):
        """Move a ticket to a different column."""
        ticket = self.get_object()
        column_id = request.data.get('column_id')
        new_position = request.data.get('position_in_column')
        
        if not column_id:
            return Response(
                {'error': 'column_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_column = TicketColumn.objects.get(id=column_id)
        except TicketColumn.DoesNotExist:
            return Response(
                {'error': 'Column not found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            old_column = ticket.column
            
            # Remove ticket from old column and adjust positions
            if old_column:
                Ticket.objects.filter(
                    column=old_column,
                    position_in_column__gt=ticket.position_in_column
                ).update(position_in_column=F('position_in_column') - 1)
            
            # Add ticket to new column
            if new_position is not None:
                # Insert at specific position
                Ticket.objects.filter(
                    column=new_column,
                    position_in_column__gte=new_position
                ).update(position_in_column=F('position_in_column') + 1)
                ticket.position_in_column = new_position
            else:
                # Add to end of column
                max_position = Ticket.objects.filter(column=new_column).aggregate(
                    max_pos=Max('position_in_column')
                )['max_pos'] or 0
                ticket.position_in_column = max_position + 1
            
            ticket.column = new_column
            ticket.save()
        
        serializer = self.get_serializer(ticket)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'], permission_classes=[permissions.IsAuthenticated])
    def reorder_in_column(self, request, pk=None):
        """Reorder a ticket within its current column."""
        ticket = self.get_object()
        new_position = request.data.get('position_in_column')
        
        if new_position is None:
            return Response(
                {'error': 'position_in_column is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_position = int(new_position)
        except ValueError:
            return Response(
                {'error': 'position_in_column must be a number'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not ticket.column:
            return Response(
                {'error': 'Ticket is not assigned to any column'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            # Update positions of other tickets in the same column
            if new_position > ticket.position_in_column:
                # Moving down - decrease position of tickets in between
                Ticket.objects.filter(
                    column=ticket.column,
                    position_in_column__gt=ticket.position_in_column,
                    position_in_column__lte=new_position
                ).update(position_in_column=F('position_in_column') - 1)
            else:
                # Moving up - increase position of tickets in between
                Ticket.objects.filter(
                    column=ticket.column,
                    position_in_column__gte=new_position,
                    position_in_column__lt=ticket.position_in_column
                ).update(position_in_column=F('position_in_column') + 1)
            
            # Update the ticket's position
            ticket.position_in_column = new_position
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
