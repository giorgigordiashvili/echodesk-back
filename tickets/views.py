from rest_framework import viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, F, Max, Count
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from drf_spectacular.openapi import OpenApiTypes
from .models import (
    Ticket, Tag, TicketComment, TicketColumn, SubTicket, ChecklistItem,
    TicketAssignment, SubTicketAssignment, TicketTimeLog, Board, TicketPayment,
    ItemList, ListItem, TicketForm, TicketFormSubmission
)
from .serializers import (
    TicketSerializer, TicketListSerializer, TagSerializer,
    TicketCommentSerializer, TicketColumnSerializer,
    TicketColumnCreateSerializer, TicketColumnUpdateSerializer,
    KanbanBoardSerializer, SubTicketSerializer, ChecklistItemSerializer,
    TicketAssignmentSerializer, SubTicketAssignmentSerializer, TicketTimeLogSerializer,
    TimeTrackingSummarySerializer, BoardSerializer, TicketPaymentSerializer,
    ItemListSerializer, ItemListMinimalSerializer, ListItemSerializer, ListItemMinimalSerializer,
    TicketFormSerializer, TicketFormMinimalSerializer, TicketFormSubmissionSerializer
)


class BoardPermission(permissions.BasePermission):
    """
    Custom permission class for Board operations.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        # Check permissions based on action
        if view.action == 'list' or view.action == 'retrieve' or view.action == 'kanban_board':
            # Allow access if user has full board permissions OR order access permissions
            return (request.user.has_permission('view_boards') or 
                   request.user.has_permission('access_orders'))
        elif view.action == 'create':
            return request.user.has_permission('create_boards')
        elif view.action in ['update', 'partial_update']:
            return request.user.has_permission('edit_boards')
        elif view.action == 'destroy':
            return request.user.has_permission('delete_boards')
        else:
            # Default to view permission for unknown actions
            return (request.user.has_permission('view_boards') or 
                   request.user.has_permission('access_orders'))
    
    def has_object_permission(self, request, view, obj):
        # For object-level permissions, we can add additional checks
        # For now, rely on the general permission check
        return self.has_permission(request, view)


class TicketColumnViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ticket columns (Kanban board columns).
    """
    queryset = TicketColumn.objects.all()
    serializer_class = TicketColumnSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['board']
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
        Only superadmins can create, update, or delete columns.
        Anyone authenticated can view columns.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'reorder']:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def check_superadmin_permission(self, request):
        """Check if user is superadmin."""
        if not request.user.is_superuser:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only superadmin users can manage ticket statuses.")
    
    def create(self, request, *args, **kwargs):
        """Create a new ticket column (superadmin only)."""
        self.check_superadmin_permission(request)
        return super().create(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Update a ticket column (superadmin only)."""
        self.check_superadmin_permission(request)
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """Partially update a ticket column (superadmin only)."""
        self.check_superadmin_permission(request)
        return super().partial_update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        """Delete a ticket column (superadmin only)."""
        self.check_superadmin_permission(request)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def reorder(self, request, pk=None):
        """Reorder columns (superadmin only)."""
        self.check_superadmin_permission(request)
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
        # Get board_id from query params, default to default board
        board_id = request.query_params.get('board_id')
        
        if board_id:
            try:
                board = Board.objects.get(id=board_id)
                columns = TicketColumn.objects.filter(board=board).order_by('position')
            except Board.DoesNotExist:
                return Response({'error': 'Board not found'}, status=404)
        else:
            # Get default board or first available board
            default_board = Board.objects.filter(is_default=True).first()
            if not default_board:
                default_board = Board.objects.first()
            
            if default_board:
                columns = TicketColumn.objects.filter(board=default_board).order_by('position')
            else:
                # Fallback to columns without board (legacy support)
                columns = TicketColumn.objects.filter(board__isnull=True).order_by('position')
        
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

        # Check if user belongs to any group assigned to the ticket
        user_groups = request.user.tenant_groups.all()
        is_in_assigned_group = obj.assigned_groups.filter(id__in=user_groups).exists()

        # Users can view tickets they created, are assigned to, or belong to an assigned group
        if request.method in permissions.SAFE_METHODS:
            return (obj.created_by == request.user or
                   obj.assigned_to == request.user or
                   obj.assigned_users.filter(id=request.user.id).exists() or
                   is_in_assigned_group)

        # Only staff can assign tickets or move to closed columns
        if request.method in ['PUT', 'PATCH']:
            # Check if trying to assign ticket or move to closed column
            if 'assigned_to_id' in request.data or 'assigned_group_ids' in request.data:
                return request.user.is_staff
            # Check if trying to move to a closed status column
            if 'column_id' in request.data:
                try:
                    column = TicketColumn.objects.get(id=request.data['column_id'])
                    if column.is_closed_status:
                        return request.user.is_staff
                except TicketColumn.DoesNotExist:
                    pass
            # Users can edit tickets they created, are assigned to, or belong to an assigned group (but not assign or close)
            return (obj.created_by == request.user or
                   obj.assigned_to == request.user or
                   obj.assigned_users.filter(id=request.user.id).exists() or
                   is_in_assigned_group)

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
    ).prefetch_related('tags', 'comments', 'assigned_groups')
    serializer_class = TicketSerializer
    permission_classes = [TicketPermission]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['priority', 'assigned_to', 'created_by', 'tags', 'column', 'assigned_groups']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'priority']
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
            user_groups = self.request.user.tenant_groups.all()
            queryset = queryset.filter(
                Q(created_by=self.request.user) |
                Q(assigned_to=self.request.user) |
                Q(assigned_users=self.request.user) |
                Q(assigned_groups__in=user_groups)
            ).distinct()

        # Additional filtering by query parameters
        priority_filter = self.request.query_params.get('priority')
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)

        assigned_to_filter = self.request.query_params.get('assigned_to')
        if assigned_to_filter:
            queryset = queryset.filter(assigned_to_id=assigned_to_filter)

        created_by_filter = self.request.query_params.get('created_by')
        if created_by_filter:
            queryset = queryset.filter(created_by_id=created_by_filter)

        assigned_group_filter = self.request.query_params.get('assigned_group')
        if assigned_group_filter:
            queryset = queryset.filter(assigned_groups__id=assigned_group_filter)

        return queryset

    def perform_create(self, serializer):
        """Create a ticket and start time tracking if applicable."""
        # Set the user who created the ticket
        ticket = serializer.save(created_by=self.request.user)
        
        # If the assigned column has time tracking enabled, create initial time log
        if ticket.column and ticket.column.track_time:
            TicketTimeLog.objects.create(
                ticket=ticket,
                column=ticket.column,
                user=self.request.user
            )

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
        queryset = self.queryset.filter(
            Q(assigned_to=request.user) |
            Q(assigned_users=request.user)
        )
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
            
            # Handle time tracking for old column (if enabled and ticket is leaving a column)
            if old_column and old_column.track_time:
                # Find the active time log for this ticket in the old column
                active_time_log = TicketTimeLog.objects.filter(
                    ticket=ticket,
                    column=old_column,
                    exited_at__isnull=True
                ).first()
                
                if active_time_log:
                    from django.utils import timezone
                    active_time_log.exited_at = timezone.now()
                    active_time_log.calculate_duration()
            
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
            
            # Handle time tracking for new column (if enabled)
            if new_column.track_time:
                # Create a new time log entry for the new column
                TicketTimeLog.objects.create(
                    ticket=ticket,
                    column=new_column,
                    user=request.user
                )
        
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
            Q(ticket__assigned_to=self.request.user) |
            Q(ticket__assigned_users=self.request.user)
        ).select_related('user', 'ticket')

    def perform_create(self, serializer):
        """Set the user when creating a comment."""
        serializer.save(user=self.request.user)


class SubTicketViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing sub-tickets.
    """
    serializer_class = SubTicketSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['parent_ticket', 'priority', 'is_completed', 'assigned_to', 'created_by']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'updated_at', 'priority', 'position']
    ordering = ['position', 'created_at']

    def get_queryset(self):
        """Filter sub-tickets based on user permissions."""
        if self.request.user.is_staff:
            return SubTicket.objects.all().select_related(
                'parent_ticket', 'created_by', 'assigned_to'
            ).prefetch_related('checklist_items')
        
        # Non-staff users can only see sub-tickets for tickets they have access to
        return SubTicket.objects.filter(
            Q(parent_ticket__created_by=self.request.user) | 
            Q(parent_ticket__assigned_to=self.request.user) |
            Q(parent_ticket__assigned_users=self.request.user) |
            Q(created_by=self.request.user) |
            Q(assigned_to=self.request.user) |
            Q(assigned_users=self.request.user)
        ).select_related(
            'parent_ticket', 'created_by', 'assigned_to'
        ).prefetch_related('checklist_items')

    @action(detail=True, methods=['patch'])
    def toggle_completion(self, request, pk=None):
        """Toggle the completion status of a sub-ticket."""
        sub_ticket = self.get_object()
        sub_ticket.is_completed = not sub_ticket.is_completed
        sub_ticket.save()
        serializer = self.get_serializer(sub_ticket)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def reorder(self, request, pk=None):
        """Reorder sub-ticket within its parent ticket."""
        sub_ticket = self.get_object()
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
            # Update positions of other sub-tickets in the same parent
            if new_position > sub_ticket.position:
                # Moving down
                SubTicket.objects.filter(
                    parent_ticket=sub_ticket.parent_ticket,
                    position__gt=sub_ticket.position,
                    position__lte=new_position
                ).update(position=F('position') - 1)
            else:
                # Moving up
                SubTicket.objects.filter(
                    parent_ticket=sub_ticket.parent_ticket,
                    position__gte=new_position,
                    position__lt=sub_ticket.position
                ).update(position=F('position') + 1)
            
            # Update the sub-ticket's position
            sub_ticket.position = new_position
            sub_ticket.save()
        
        serializer = self.get_serializer(sub_ticket)
        return Response(serializer.data)


class ChecklistItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing checklist items.
    """
    serializer_class = ChecklistItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['ticket', 'sub_ticket', 'is_checked', 'created_by']
    ordering_fields = ['created_at', 'position']
    ordering = ['position', 'created_at']

    def get_queryset(self):
        """Filter checklist items based on user permissions."""
        if self.request.user.is_staff:
            return ChecklistItem.objects.all().select_related(
                'ticket', 'sub_ticket', 'created_by'
            )
        
        # Non-staff users can only see checklist items for tickets they have access to
        return ChecklistItem.objects.filter(
            Q(ticket__created_by=self.request.user) | 
            Q(ticket__assigned_to=self.request.user) |
            Q(ticket__assigned_users=self.request.user) |
            Q(sub_ticket__parent_ticket__created_by=self.request.user) |
            Q(sub_ticket__parent_ticket__assigned_to=self.request.user) |
            Q(sub_ticket__parent_ticket__assigned_users=self.request.user) |
            Q(created_by=self.request.user)
        ).select_related('ticket', 'sub_ticket', 'created_by')

    @action(detail=True, methods=['patch'])
    def toggle_check(self, request, pk=None):
        """Toggle the checked status of a checklist item."""
        item = self.get_object()
        item.is_checked = not item.is_checked
        item.save()
        serializer = self.get_serializer(item)
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def reorder(self, request, pk=None):
        """Reorder checklist item within its parent (ticket or sub-ticket)."""
        item = self.get_object()
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
            # Determine the parent and filter other items
            if item.ticket:
                other_items = ChecklistItem.objects.filter(ticket=item.ticket)
            else:
                other_items = ChecklistItem.objects.filter(sub_ticket=item.sub_ticket)
            
            # Update positions
            if new_position > item.position:
                # Moving down
                other_items.filter(
                    position__gt=item.position,
                    position__lte=new_position
                ).update(position=F('position') - 1)
            else:
                # Moving up
                other_items.filter(
                    position__gte=new_position,
                    position__lt=item.position
                ).update(position=F('position') + 1)
            
            # Update the item's position
            item.position = new_position
            item.save()
        
        serializer = self.get_serializer(item)
        return Response(serializer.data)


class TicketAssignmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing ticket assignments."""
    serializer_class = TicketAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return assignments for a specific ticket."""
        ticket_pk = self.kwargs.get('ticket_pk')
        if ticket_pk:
            return TicketAssignment.objects.filter(ticket_id=ticket_pk)
        return TicketAssignment.objects.none()
    
    def perform_create(self, serializer):
        """Create a new ticket assignment."""
        ticket_pk = self.kwargs.get('ticket_pk')
        ticket = Ticket.objects.get(pk=ticket_pk)
        serializer.save(ticket=ticket, assigned_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def bulk_assign(self, request, ticket_pk=None):
        """Bulk assign users to a ticket."""
        ticket = Ticket.objects.get(pk=ticket_pk)
        user_ids = request.data.get('user_ids', [])
        roles = request.data.get('roles', {})
        
        # Clear existing assignments if replace is True
        if request.data.get('replace', False):
            TicketAssignment.objects.filter(ticket=ticket).delete()
        
        assignments = []
        for user_id in user_ids:
            role = roles.get(str(user_id), 'collaborator')
            assignment, created = TicketAssignment.objects.get_or_create(
                ticket=ticket,
                user_id=user_id,
                defaults={'role': role, 'assigned_by': request.user}
            )
            assignments.append(assignment)
        
        serializer = TicketAssignmentSerializer(assignments, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['delete'])
    def bulk_unassign(self, request, ticket_pk=None):
        """Bulk remove user assignments from a ticket."""
        ticket = Ticket.objects.get(pk=ticket_pk)
        user_ids = request.data.get('user_ids', [])
        
        deleted_count, _ = TicketAssignment.objects.filter(
            ticket=ticket,
            user_id__in=user_ids
        ).delete()
        
        return Response(
            {'message': f'Removed {deleted_count} assignments'}, 
            status=status.HTTP_204_NO_CONTENT
        )


class SubTicketAssignmentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing sub-ticket assignments."""
    serializer_class = SubTicketAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return assignments for a specific sub-ticket."""
        sub_ticket_pk = self.kwargs.get('sub_ticket_pk')
        if sub_ticket_pk:
            return SubTicketAssignment.objects.filter(sub_ticket_id=sub_ticket_pk)
        return SubTicketAssignment.objects.none()
    
    def perform_create(self, serializer):
        """Create a new sub-ticket assignment."""
        sub_ticket_pk = self.kwargs.get('sub_ticket_pk')
        sub_ticket = SubTicket.objects.get(pk=sub_ticket_pk)
        serializer.save(sub_ticket=sub_ticket, assigned_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def bulk_assign(self, request, sub_ticket_pk=None):
        """Bulk assign users to a sub-ticket."""
        sub_ticket = SubTicket.objects.get(pk=sub_ticket_pk)
        user_ids = request.data.get('user_ids', [])
        roles = request.data.get('roles', {})
        
        # Clear existing assignments if replace is True
        if request.data.get('replace', False):
            SubTicketAssignment.objects.filter(sub_ticket=sub_ticket).delete()
        
        assignments = []
        for user_id in user_ids:
            role = roles.get(str(user_id), 'collaborator')
            assignment, created = SubTicketAssignment.objects.get_or_create(
                sub_ticket=sub_ticket,
                user_id=user_id,
                defaults={'role': role, 'assigned_by': request.user}
            )
            assignments.append(assignment)
        
        serializer = SubTicketAssignmentSerializer(assignments, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['delete'])
    def bulk_unassign(self, request, sub_ticket_pk=None):
        """Bulk remove user assignments from a sub-ticket."""
        sub_ticket = SubTicket.objects.get(pk=sub_ticket_pk)
        user_ids = request.data.get('user_ids', [])
        
        deleted_count, _ = SubTicketAssignment.objects.filter(
            sub_ticket=sub_ticket,
            user_id__in=user_ids
        ).delete()
        
        return Response(
            {'message': f'Removed {deleted_count} assignments'}, 
            status=status.HTTP_204_NO_CONTENT
        )


@extend_schema(tags=['Time Tracking'])
class TicketTimeLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing ticket time logs."""
    serializer_class = TicketTimeLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['ticket', 'column', 'user']
    ordering_fields = ['entered_at', 'exited_at', 'duration_seconds']
    ordering = ['-entered_at']
    
    def get_queryset(self):
        """Return time logs for tickets the user has access to."""
        if self.request.user.is_staff:
            return TicketTimeLog.objects.all().select_related(
                'ticket', 'column', 'user'
            )
        
        # Non-staff users can only see time logs for tickets they have access to
        return TicketTimeLog.objects.filter(
            Q(ticket__created_by=self.request.user) | 
            Q(ticket__assigned_to=self.request.user) |
            Q(ticket__assigned_users=self.request.user)
        ).select_related('ticket', 'column', 'user')
    
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name='days',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of days to include in summary (default: 30)',
                default=30
            )
        ],
        responses={200: TimeTrackingSummarySerializer},
        tags=['Time Tracking']
    )
    @action(detail=False, methods=['get'])
    def my_time_summary(self, request):
        """Get time tracking summary for the current user."""
        from django.db.models import Sum, Count, Avg
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        # Get date range from query params (default to last 30 days)
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Base queryset for user's time logs
        user_logs = TicketTimeLog.objects.filter(
            user=request.user,
            entered_at__gte=start_date
        ).select_related('ticket', 'column')
        
        # Total time tracked
        total_time = user_logs.filter(
            duration_seconds__isnull=False
        ).aggregate(
            total_seconds=Sum('duration_seconds'),
            total_sessions=Count('id')
        )
        
        # Time by column
        time_by_column = user_logs.filter(
            duration_seconds__isnull=False
        ).values(
            'column__name', 'column__color'
        ).annotate(
            total_seconds=Sum('duration_seconds'),
            session_count=Count('id'),
            avg_seconds=Avg('duration_seconds')
        ).order_by('-total_seconds')
        
        # Recent activity
        recent_logs = user_logs.order_by('-entered_at')[:10]
        recent_logs_data = TicketTimeLogSerializer(recent_logs, many=True).data
        
        # Currently active sessions
        active_sessions = user_logs.filter(
            exited_at__isnull=True
        )
        active_sessions_data = TicketTimeLogSerializer(active_sessions, many=True).data
        
        # Daily breakdown for the period
        daily_stats = {}
        for log in user_logs.filter(duration_seconds__isnull=False):
            date_key = log.entered_at.date().isoformat()
            if date_key not in daily_stats:
                daily_stats[date_key] = {
                    'date': date_key,
                    'total_seconds': 0,
                    'session_count': 0
                }
            daily_stats[date_key]['total_seconds'] += log.duration_seconds or 0
            daily_stats[date_key]['session_count'] += 1
        
        daily_breakdown = list(daily_stats.values())
        daily_breakdown.sort(key=lambda x: x['date'], reverse=True)
        
        return Response({
            'period_days': days,
            'start_date': start_date,
            'total_time_seconds': total_time['total_seconds'] or 0,
            'total_sessions': total_time['total_sessions'] or 0,
            'time_by_column': list(time_by_column),
            'daily_breakdown': daily_breakdown,
            'recent_activity': recent_logs_data,
            'active_sessions': active_sessions_data
        })


class BoardViewSet(viewsets.ModelViewSet):
    """ViewSet for managing kanban boards."""
    serializer_class = BoardSerializer
    permission_classes = [BoardPermission]
    
    def get_queryset(self):
        """Return boards the user can access."""
        user = self.request.user
        
        # Check if user has full board access permissions
        if user.has_permission('view_boards'):
            # Full board access - show all boards
            return Board.objects.all()
        
        # Check if user has order permissions but not full board permissions (for order users)
        if user.has_permission('access_orders'):
            # User only has order permissions - filter to boards they're attached to
            user_attached_boards = Board.objects.filter(order_users=user)
            
            if user_attached_boards.exists():
                # User is attached to specific boards - show only those
                return user_attached_boards
            else:
                # User is not attached to specific boards - show boards that have no order users assigned
                # (meaning they are open to all order users)
                return Board.objects.annotate(
                    order_users_count=Count('order_users')
                ).filter(order_users_count=0)
        
        # User has no relevant permissions - return empty queryset
        return Board.objects.none()
    
    def perform_create(self, serializer):
        """Set the created_by field when creating a board."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def kanban_board(self, request, pk=None):
        """Get kanban board data for a specific board."""
        board = self.get_object()
        
        # Get columns for this board
        columns = TicketColumn.objects.filter(board=board).order_by('position')
        
        # Build response similar to existing kanban_board endpoint
        columns_data = []
        tickets_by_column = {}
        
        for column in columns:
            column_serializer = TicketColumnSerializer(column, context={'request': request})
            columns_data.append(column_serializer.data)
            
            # Get tickets for this column
            tickets = Ticket.objects.filter(column=column).order_by('position_in_column')
            tickets_serializer = TicketListSerializer(tickets, many=True, context={'request': request})
            tickets_by_column[column.id] = tickets_serializer.data
        
        return Response({
            'board': BoardSerializer(board, context={'request': request}).data,
            'columns': columns_data,
            'tickets_by_column': tickets_by_column
        })
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set this board as the default board."""
        board = self.get_object()
        board.is_default = True
        board.save()
        return Response({'status': 'default set'})
    
    @action(detail=False, methods=['get'])
    def default(self, request):
        """Get the default board."""
        default_board = Board.objects.filter(is_default=True).first()
        if not default_board:
            # If no default exists, create one or use the first available
            first_board = Board.objects.first()
            if first_board:
                first_board.is_default = True
                first_board.save()
                default_board = first_board
        
        if default_board:
            return Response(BoardSerializer(default_board, context={'request': request}).data)
        return Response({'error': 'No boards found'}, status=404)


class TicketPaymentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing ticket payments.
    """
    queryset = TicketPayment.objects.all()
    serializer_class = TicketPaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['ticket', 'payment_method', 'currency']
    ordering = ['-processed_at']

    def get_queryset(self):
        """Filter payments based on user permissions."""
        queryset = super().get_queryset()
        
        # If user has ticket permissions or is superuser, return all
        if (self.request.user.is_superuser or 
            self.request.user.has_permission('view_tickets')):
            return queryset
        
        # Otherwise, filter to tickets the user can access
        accessible_tickets = Ticket.objects.filter(
            Q(created_by=self.request.user) |
            Q(assigned_to=self.request.user) |
            Q(assigned_users=self.request.user)
        ).distinct()
        
        return queryset.filter(ticket__in=accessible_tickets)

    @action(detail=False, methods=['post'])
    def process_payment(self, request):
        """Process a payment for a ticket."""
        ticket_id = request.data.get('ticket_id')
        amount = request.data.get('amount')
        
        if not ticket_id or not amount:
            return Response(
                {'error': 'ticket_id and amount are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            ticket = Ticket.objects.get(id=ticket_id)
            amount = float(amount)
        except (Ticket.DoesNotExist, ValueError):
            return Response(
                {'error': 'Invalid ticket or amount'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user can modify this ticket
        if not (request.user.is_superuser or 
                request.user.has_permission('edit_tickets') or
                ticket.created_by == request.user):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            remaining_balance = ticket.add_payment(amount, request.user)
            
            # Get updated ticket data
            updated_ticket = Ticket.objects.get(id=ticket_id)
            ticket_serializer = TicketSerializer(updated_ticket, context={'request': request})
            
            return Response({
                'message': 'Payment processed successfully',
                'remaining_balance': remaining_balance,
                'ticket': ticket_serializer.data
            })
        except ValueError as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def payment_summary(self, request):
        """Get payment summary across all accessible tickets."""
        from django.db.models import Sum, Count, Q
        from decimal import Decimal
        
        # Get accessible tickets
        accessible_tickets = Ticket.objects.all()
        if not (request.user.is_superuser or request.user.has_permission('view_tickets')):
            accessible_tickets = accessible_tickets.filter(
                Q(created_by=request.user) |
                Q(assigned_to=request.user) |
                Q(assigned_users=request.user)
            ).distinct()
        
        # Filter by board if provided
        board_id = request.query_params.get('board_id')
        if board_id:
            accessible_tickets = accessible_tickets.filter(column__board_id=board_id)
        
        summary = accessible_tickets.aggregate(
            total_tickets=Count('id'),
            billable_tickets=Count('id', filter=Q(price__gt=0)),
            total_value=Sum('price'),
            total_paid=Sum('amount_paid'),
            paid_tickets=Count('id', filter=Q(is_paid=True)),
            unpaid_tickets=Count('id', filter=Q(is_paid=False, price__gt=0)),
            overdue_tickets=Count('id', filter=Q(
                is_paid=False, 
                payment_due_date__lt=timezone.now().date()
            ))
        )
        
        # Calculate remaining balance
        total_value = summary['total_value'] or Decimal('0.00')
        total_paid = summary['total_paid'] or Decimal('0.00')
        summary['remaining_balance'] = total_value - total_paid
        
        return Response(summary)


# ============================================================================
# New ViewSets for ItemList, ListItem, TicketForm, and TicketFormSubmission
# ============================================================================

class ItemListViewSet(viewsets.ModelViewSet):
    """ViewSet for managing item lists."""
    queryset = ItemList.objects.all()
    serializer_class = ItemListSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter lists based on user permissions."""
        queryset = super().get_queryset()
        
        # Filter by is_active if specified
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset

    def get_serializer_class(self):
        """Use minimal serializer for list action."""
        if self.action == 'list':
            return ItemListMinimalSerializer
        return ItemListSerializer

    @action(detail=True, methods=['get'])
    def root_items(self, request, pk=None):
        """Get only root-level items for this list."""
        item_list = self.get_object()
        root_items = item_list.items.filter(parent__isnull=True, is_active=True)
        serializer = ListItemSerializer(root_items, many=True, context={'request': request})
        return Response(serializer.data)


class ListItemViewSet(viewsets.ModelViewSet):
    """ViewSet for managing list items."""
    queryset = ListItem.objects.all()
    serializer_class = ListItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['item_list', 'parent', 'is_active']
    search_fields = ['label', 'custom_id']
    ordering = ['position', 'created_at']

    def get_queryset(self):
        """Filter items based on user permissions."""
        queryset = super().get_queryset()
        
        # Filter by list if specified
        item_list_id = self.request.query_params.get('item_list_id')
        if item_list_id:
            queryset = queryset.filter(item_list_id=item_list_id)
        
        # Filter by is_active if specified
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter only root items if specified
        root_only = self.request.query_params.get('root_only')
        if root_only and root_only.lower() == 'true':
            queryset = queryset.filter(parent__isnull=True)
        
        return queryset

    def get_serializer_class(self):
        """Use minimal serializer for list action to avoid deep nesting."""
        if self.action == 'list':
            return ListItemMinimalSerializer
        return ListItemSerializer

    @action(detail=True, methods=['get'])
    def children(self, request, pk=None):
        """Get direct children of this item."""
        item = self.get_object()
        children = item.children.filter(is_active=True)
        serializer = ListItemSerializer(children, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def all_descendants(self, request, pk=None):
        """Get all descendants of this item recursively."""
        item = self.get_object()
        descendants = item.get_all_children()
        serializer = ListItemMinimalSerializer(descendants, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['patch'])
    def reorder(self, request, pk=None):
        """Reorder item within its parent or list."""
        item = self.get_object()
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
            # Determine the siblings
            if item.parent:
                siblings = ListItem.objects.filter(
                    item_list=item.item_list,
                    parent=item.parent
                )
            else:
                siblings = ListItem.objects.filter(
                    item_list=item.item_list,
                    parent__isnull=True
                )
            
            # Update positions
            if new_position > item.position:
                # Moving down
                siblings.filter(
                    position__gt=item.position,
                    position__lte=new_position
                ).update(position=F('position') - 1)
            else:
                # Moving up
                siblings.filter(
                    position__gte=new_position,
                    position__lt=item.position
                ).update(position=F('position') + 1)
            
            # Update the item's position
            item.position = new_position
            item.save()
        
        serializer = self.get_serializer(item)
        return Response(serializer.data)


class TicketFormViewSet(viewsets.ModelViewSet):
    """ViewSet for managing ticket forms."""
    queryset = TicketForm.objects.all()
    serializer_class = TicketFormSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter forms based on user permissions."""
        queryset = super().get_queryset()
        
        # Filter by is_active if specified
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by is_default if specified
        is_default = self.request.query_params.get('is_default')
        if is_default is not None:
            queryset = queryset.filter(is_default=is_default.lower() == 'true')
        
        return queryset

    def get_serializer_class(self):
        """Use minimal serializer for list action."""
        if self.action == 'list':
            return TicketFormMinimalSerializer
        return TicketFormSerializer

    @action(detail=False, methods=['get'])
    def default(self, request):
        """Get the default form."""
        default_form = TicketForm.objects.filter(is_default=True, is_active=True).first()
        if not default_form:
            # If no default, use the first active form
            default_form = TicketForm.objects.filter(is_active=True).first()
        
        if default_form:
            serializer = TicketFormSerializer(default_form, context={'request': request})
            return Response(serializer.data)
        return Response({'error': 'No forms found'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set this form as the default form."""
        form = self.get_object()
        form.is_default = True
        form.save()
        return Response({'status': 'default set'})

    @action(detail=True, methods=['get'])
    def with_lists(self, request, pk=None):
        """Get form with full list details (including items)."""
        form = self.get_object()
        serializer = TicketFormSerializer(form, context={'request': request})
        return Response(serializer.data)


class TicketFormSubmissionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing ticket form submissions."""
    queryset = TicketFormSubmission.objects.all()
    serializer_class = TicketFormSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['form', 'ticket', 'submitted_by']
    ordering = ['-submitted_at']

    def get_queryset(self):
        """Filter submissions based on user permissions."""
        queryset = super().get_queryset()
        
        # Non-staff users can only see submissions for tickets they have access to
        if not self.request.user.is_staff:
            queryset = queryset.filter(
                Q(ticket__created_by=self.request.user) | 
                Q(ticket__assigned_to=self.request.user) |
                Q(ticket__assigned_users=self.request.user) |
                Q(submitted_by=self.request.user)
            )
        
        return queryset

    @action(detail=False, methods=['get'])
    def by_form(self, request):
        """Get submissions grouped by form."""
        form_id = request.query_params.get('form_id')
        if not form_id:
            return Response(
                {'error': 'form_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().filter(form_id=form_id)
        serializer = TicketFormSubmissionSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_ticket(self, request):
        """Get submission for a specific ticket."""
        ticket_id = request.query_params.get('ticket_id')
        if not ticket_id:
            return Response(
                {'error': 'ticket_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            submission = self.get_queryset().get(ticket_id=ticket_id)
            serializer = TicketFormSubmissionSerializer(submission, context={'request': request})
            return Response(serializer.data)
        except TicketFormSubmission.DoesNotExist:
            return Response({'error': 'Submission not found'}, status=status.HTTP_404_NOT_FOUND)
