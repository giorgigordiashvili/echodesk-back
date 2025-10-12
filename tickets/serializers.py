from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Ticket, Tag, TicketComment, TicketColumn, SubTicket, ChecklistItem,
    TicketAssignment, SubTicketAssignment, TicketTimeLog, Board, TicketPayment,
    ItemList, ListItem, TicketForm, TicketFormSubmission
)

User = get_user_model()


class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal user serializer for ticket relationships."""
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']
        read_only_fields = ['id', 'email', 'first_name', 'last_name']


class BoardSerializer(serializers.ModelSerializer):
    """Serializer for Board model."""
    created_by = serializers.StringRelatedField(read_only=True)
    columns_count = serializers.SerializerMethodField()
    order_users = UserMinimalSerializer(many=True, read_only=True)
    order_user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text='List of user IDs who can create orders on this board'
    )
    payment_summary = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = Board
        fields = [
            'id', 'name', 'description', 'is_default',
            'created_at', 'updated_at', 'created_by', 'columns_count',
            'order_users', 'order_user_ids', 'payment_summary'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def get_columns_count(self, obj):
        return obj.columns.count()
    
    def get_payment_summary(self, obj):
        """Get payment summary for this board."""
        return obj.get_payment_summary()
    
    def create(self, validated_data):
        order_user_ids = validated_data.pop('order_user_ids', [])
        validated_data['created_by'] = self.context['request'].user
        board = super().create(validated_data)
        
        if order_user_ids:
            board.order_users.set(order_user_ids)
        
        return board
    
    def update(self, instance, validated_data):
        order_user_ids = validated_data.pop('order_user_ids', None)
        board = super().update(instance, validated_data)
        
        if order_user_ids is not None:
            board.order_users.set(order_user_ids)
        
        return board


class TicketColumnSerializer(serializers.ModelSerializer):
    """Serializer for TicketColumn model."""
    created_by = serializers.StringRelatedField(read_only=True)
    tickets_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TicketColumn
        fields = [
            'id', 'name', 'description', 'color', 'position', 
            'is_default', 'is_closed_status', 'track_time', 'board', 'created_at', 'updated_at',
            'created_by', 'tickets_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_tickets_count(self, obj):
        """Get the number of tickets in this column."""
        return obj.tickets.count()

    def create(self, validated_data):
        # Set created_by from request context
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def validate_color(self, value):
        """Validate that color is a valid hex color code."""
        import re
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise serializers.ValidationError('Color must be a valid hex color code (e.g., #3B82F6)')
        return value


class TicketColumnCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating ticket columns."""
    
    class Meta:
        model = TicketColumn
        fields = ['name', 'description', 'color', 'position', 'is_default', 'is_closed_status', 'track_time', 'board']
        
    def create(self, validated_data):
        # Set created_by from request context
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class TicketColumnUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating ticket columns."""
    
    class Meta:
        model = TicketColumn
        fields = ['name', 'description', 'color', 'position', 'is_default', 'is_closed_status', 'track_time', 'board']


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model."""
    
    class Meta:
        model = Tag
        fields = ['id', 'name', 'created_at']
        read_only_fields = ['created_at']


class TicketPaymentSerializer(serializers.ModelSerializer):
    """Serializer for TicketPayment model."""
    processed_by = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = TicketPayment
        fields = [
            'id', 'ticket', 'amount', 'currency', 'payment_method',
            'payment_reference', 'notes', 'processed_by', 'processed_at'
        ]
        read_only_fields = ['id', 'processed_at', 'processed_by']
    
    def create(self, validated_data):
        # Set processed_by from request context
        validated_data['processed_by'] = self.context['request'].user
        return super().create(validated_data)



class TicketAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for TicketAssignment model."""
    user = UserMinimalSerializer(read_only=True)
    assigned_by = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = TicketAssignment
        fields = ['id', 'user', 'role', 'assigned_at', 'assigned_by']
        read_only_fields = ['id', 'assigned_at', 'assigned_by']


class SubTicketAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for SubTicketAssignment model."""
    user = UserMinimalSerializer(read_only=True)
    assigned_by = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = SubTicketAssignment
        fields = ['id', 'user', 'role', 'assigned_at', 'assigned_by']
        read_only_fields = ['id', 'assigned_at', 'assigned_by']


class TicketCommentSerializer(serializers.ModelSerializer):
    """Serializer for TicketComment model."""
    user = UserMinimalSerializer(read_only=True)
    user_id = serializers.IntegerField(write_only=True, required=False)
    
    class Meta:
        model = TicketComment
        fields = ['id', 'ticket', 'user', 'user_id', 'comment', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        # Set user from request context if not provided
        if 'user_id' not in validated_data:
            validated_data['user'] = self.context['request'].user
        else:
            user_id = validated_data.pop('user_id')
            validated_data['user'] = User.objects.get(id=user_id)
        return super().create(validated_data)


class ChecklistItemSerializer(serializers.ModelSerializer):
    """Serializer for ChecklistItem model."""
    created_by = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = ChecklistItem
        fields = [
            'id', 'ticket', 'sub_ticket', 'text', 'is_checked', 'position',
            'created_at', 'updated_at', 'created_by'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def create(self, validated_data):
        # Set created_by from request context
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

    def validate(self, data):
        """Ensure checklist item belongs to either ticket or sub_ticket, not both."""
        ticket = data.get('ticket')
        sub_ticket = data.get('sub_ticket')
        
        if not ticket and not sub_ticket:
            raise serializers.ValidationError("Checklist item must belong to either a ticket or sub_ticket.")
        
        if ticket and sub_ticket:
            raise serializers.ValidationError("Checklist item cannot belong to both ticket and sub_ticket.")
        
        return data


class SubTicketSerializer(serializers.ModelSerializer):
    """Serializer for SubTicket model."""
    created_by = UserMinimalSerializer(read_only=True)
    assigned_to = UserMinimalSerializer(read_only=True)
    assigned_to_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    assigned_users = UserMinimalSerializer(many=True, read_only=True)
    assignments = SubTicketAssignmentSerializer(source='subticketassignment_set', many=True, read_only=True)
    assigned_user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text='List of user IDs to assign to this sub-ticket'
    )
    assignment_roles = serializers.DictField(
        child=serializers.CharField(max_length=20),
        write_only=True,
        required=False,
        help_text='Dictionary mapping user IDs to roles (e.g., {"1": "primary", "2": "collaborator"})'
    )
    checklist_items = ChecklistItemSerializer(many=True, read_only=True)
    checklist_items_count = serializers.SerializerMethodField()
    completed_items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SubTicket
        fields = [
            'id', 'parent_ticket', 'title', 'description', 'rich_description',
            'description_format', 'priority', 'is_completed', 'position',
            'created_at', 'updated_at', 'created_by', 'assigned_to', 'assigned_to_id',
            'assigned_users', 'assignments', 'assigned_user_ids', 'assignment_roles',
            'checklist_items', 'checklist_items_count', 'completed_items_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_checklist_items_count(self, obj):
        """Get the number of checklist items for this sub-ticket."""
        return obj.checklist_items.count()

    def get_completed_items_count(self, obj):
        """Get the number of completed checklist items."""
        return obj.checklist_items.filter(is_checked=True).count()

    def create(self, validated_data):
        assigned_to_id = validated_data.pop('assigned_to_id', None)
        assigned_user_ids = validated_data.pop('assigned_user_ids', [])
        assignment_roles = validated_data.pop('assignment_roles', {})
        
        # Set created_by from request context
        validated_data['created_by'] = self.context['request'].user
        current_user = self.context['request'].user
        
        # Set assigned_to if provided
        if assigned_to_id:
            validated_data['assigned_to'] = User.objects.get(id=assigned_to_id)
        
        sub_ticket = super().create(validated_data)
        
        # Handle multiple user assignments
        if assigned_user_ids:
            for user_id in assigned_user_ids:
                role = assignment_roles.get(str(user_id), 'collaborator')
                SubTicketAssignment.objects.create(
                    sub_ticket=sub_ticket,
                    user_id=user_id,
                    role=role,
                    assigned_by=current_user
                )
        
        return sub_ticket

    def update(self, instance, validated_data):
        assigned_to_id = validated_data.pop('assigned_to_id', None)
        assigned_user_ids = validated_data.pop('assigned_user_ids', None)
        assignment_roles = validated_data.pop('assignment_roles', {})
        
        current_user = self.context['request'].user
        
        # Handle assigned_to field
        if assigned_to_id is not None:
            if assigned_to_id:
                validated_data['assigned_to'] = User.objects.get(id=assigned_to_id)
            else:
                validated_data['assigned_to'] = None
        
        sub_ticket = super().update(instance, validated_data)
        
        # Handle multiple user assignments update
        if assigned_user_ids is not None:
            # Clear existing assignments
            SubTicketAssignment.objects.filter(sub_ticket=sub_ticket).delete()
            
            # Add new assignments
            for user_id in assigned_user_ids:
                role = assignment_roles.get(str(user_id), 'collaborator')
                SubTicketAssignment.objects.create(
                    sub_ticket=sub_ticket,
                    user_id=user_id,
                    role=role,
                    assigned_by=current_user
                )
        
        return sub_ticket


class TicketSerializer(serializers.ModelSerializer):
    """Serializer for Ticket model."""
    created_by = UserMinimalSerializer(read_only=True)
    assigned_to = UserMinimalSerializer(read_only=True)
    assigned_to_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    assigned_users = UserMinimalSerializer(many=True, read_only=True)
    assignments = TicketAssignmentSerializer(source='ticketassignment_set', many=True, read_only=True)
    assigned_user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text='List of user IDs to assign to this ticket'
    )
    assignment_roles = serializers.DictField(
        child=serializers.CharField(max_length=20),
        write_only=True,
        required=False,
        help_text='Dictionary mapping user IDs to roles (e.g., {"1": "primary", "2": "collaborator"})'
    )
    column = TicketColumnSerializer(read_only=True)
    column_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True
    )
    comments = TicketCommentSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    # Add new fields for rich content and sub-tickets
    sub_tickets = SubTicketSerializer(many=True, read_only=True)
    sub_tickets_count = serializers.SerializerMethodField()
    completed_sub_tickets_count = serializers.SerializerMethodField()
    checklist_items = ChecklistItemSerializer(many=True, read_only=True)
    checklist_items_count = serializers.SerializerMethodField()
    completed_checklist_items_count = serializers.SerializerMethodField()
    status = serializers.ReadOnlyField()  # Dynamic status from column
    is_closed = serializers.ReadOnlyField()  # Dynamic closed status from column
    
    # Payment fields
    payments = TicketPaymentSerializer(many=True, read_only=True)
    remaining_balance = serializers.ReadOnlyField()
    payment_status = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'title', 'description', 'rich_description', 'description_format',
            'status', 'priority', 'is_closed', 'is_order', 'column', 'column_id', 'position_in_column',
            'created_at', 'updated_at', 'created_by', 'assigned_to', 'assigned_to_id',
            'assigned_users', 'assignments', 'assigned_user_ids', 'assignment_roles',
            'tags', 'tag_ids', 'comments', 'comments_count',
            'sub_tickets', 'sub_tickets_count', 'completed_sub_tickets_count',
            'checklist_items', 'checklist_items_count', 'completed_checklist_items_count',
            'price', 'currency', 'is_paid', 'amount_paid', 'payment_due_date',
            'payments', 'remaining_balance', 'payment_status', 'is_overdue'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'status', 'is_closed']

    def get_comments_count(self, obj):
        """Get the number of comments for this ticket."""
        return obj.comments.count()

    def get_sub_tickets_count(self, obj):
        """Get the number of sub-tickets for this ticket."""
        return obj.sub_tickets.count()

    def get_completed_sub_tickets_count(self, obj):
        """Get the number of completed sub-tickets."""
        return obj.sub_tickets.filter(is_completed=True).count()

    def get_checklist_items_count(self, obj):
        """Get the number of checklist items for this ticket."""
        return obj.checklist_items.count()

    def get_completed_checklist_items_count(self, obj):
        """Get the number of completed checklist items."""
        return obj.checklist_items.filter(is_checked=True).count()

    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        assigned_to_id = validated_data.pop('assigned_to_id', None)
        assigned_user_ids = validated_data.pop('assigned_user_ids', [])
        assignment_roles = validated_data.pop('assignment_roles', {})
        column_id = validated_data.pop('column_id', None)
        is_order = validated_data.get('is_order', False)
        
        # Set created_by from request context
        validated_data['created_by'] = self.context['request'].user
        current_user = self.context['request'].user
        
        # Set assigned_to if provided
        if assigned_to_id:
            validated_data['assigned_to'] = User.objects.get(id=assigned_to_id)
        
        # Handle order-specific logic
        if is_order and column_id:
            # For orders, automatically assign to the first column of the board
            column = TicketColumn.objects.get(id=column_id)
            board = column.board
            first_column = board.columns.order_by('position').first()
            if first_column:
                validated_data['column'] = first_column
            else:
                validated_data['column'] = column  # fallback to provided column
        elif column_id:
            # Set column if provided (regular tickets)
            validated_data['column'] = TicketColumn.objects.get(id=column_id)
        
        ticket = Ticket.objects.create(**validated_data)
        
        # Set tags
        if tag_ids:
            ticket.tags.set(tag_ids)
        
        # Handle multiple user assignments
        if assigned_user_ids:
            for user_id in assigned_user_ids:
                role = assignment_roles.get(str(user_id), 'collaborator')
                TicketAssignment.objects.create(
                    ticket=ticket,
                    user_id=user_id,
                    role=role,
                    assigned_by=current_user
                )
        
        return ticket

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        assigned_to_id = validated_data.pop('assigned_to_id', None)
        assigned_user_ids = validated_data.pop('assigned_user_ids', None)
        assignment_roles = validated_data.pop('assignment_roles', {})
        column_id = validated_data.pop('column_id', None)
        
        current_user = self.context['request'].user
        
        # Handle assigned_to field
        if assigned_to_id is not None:
            if assigned_to_id:
                validated_data['assigned_to'] = User.objects.get(id=assigned_to_id)
            else:
                validated_data['assigned_to'] = None
        
        # Handle column field
        if column_id is not None:
            if column_id:
                validated_data['column'] = TicketColumn.objects.get(id=column_id)
            else:
                validated_data['column'] = None
        
        ticket = super().update(instance, validated_data)
        
        # Update tags if provided
        if tag_ids is not None:
            ticket.tags.set(tag_ids)
        
        # Handle multiple user assignments update
        if assigned_user_ids is not None:
            # Clear existing assignments
            TicketAssignment.objects.filter(ticket=ticket).delete()
            
            # Add new assignments
            for user_id in assigned_user_ids:
                role = assignment_roles.get(str(user_id), 'collaborator')
                TicketAssignment.objects.create(
                    ticket=ticket,
                    user_id=user_id,
                    role=role,
                    assigned_by=current_user
                )
        
        return ticket


class TicketListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for ticket lists."""
    created_by = UserMinimalSerializer(read_only=True)
    assigned_to = UserMinimalSerializer(read_only=True)
    assigned_users = UserMinimalSerializer(many=True, read_only=True)
    assignments = TicketAssignmentSerializer(source='ticketassignment_set', many=True, read_only=True)
    column = TicketColumnSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    status = serializers.ReadOnlyField()  # Dynamic status from column
    is_closed = serializers.ReadOnlyField()  # Dynamic closed status from column
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'title', 'status', 'priority', 'is_closed', 'column', 'position_in_column',
            'created_at', 'updated_at', 'created_by', 'assigned_to', 'assigned_users', 
            'assignments', 'tags', 'comments_count'
        ]
        read_only_fields = fields

    def get_comments_count(self, obj):
        """Get the number of comments for this ticket."""
        return obj.comments.count()


class KanbanBoardSerializer(serializers.Serializer):
    """Serializer for Kanban board data with columns and tickets."""
    columns = TicketColumnSerializer(many=True, read_only=True)
    tickets_by_column = serializers.SerializerMethodField()
    
    def get_tickets_by_column(self, obj):
        """Get tickets organized by column."""
        columns = obj.get('columns', [])
        tickets_data = {}
        
        for column in columns:
            tickets = Ticket.objects.filter(column=column).order_by('position_in_column', '-created_at')
            tickets_data[column.id] = TicketListSerializer(tickets, many=True, context=self.context).data
        
        return tickets_data


class TicketTimeLogSerializer(serializers.ModelSerializer):
    """Serializer for TicketTimeLog model."""
    ticket = serializers.StringRelatedField(read_only=True)
    column = TicketColumnSerializer(read_only=True)
    user = UserMinimalSerializer(read_only=True)
    duration_display = serializers.ReadOnlyField()
    
    class Meta:
        model = TicketTimeLog
        fields = [
            'id', 'ticket', 'column', 'user', 'entered_at', 'exited_at',
            'duration_seconds', 'duration_display'
        ]
        read_only_fields = fields


class TimeTrackingSummarySerializer(serializers.Serializer):
    """Serializer for time tracking summary data."""
    period_days = serializers.IntegerField()
    start_date = serializers.DateTimeField()
    total_time_seconds = serializers.IntegerField()
    total_sessions = serializers.IntegerField()
    time_by_column = serializers.ListField()
    daily_breakdown = serializers.ListField()
    recent_activity = TicketTimeLogSerializer(many=True)
    active_sessions = TicketTimeLogSerializer(many=True)


# ============================================================================
# New Serializers for ItemList, ListItem, TicketForm, and TicketFormSubmission
# ============================================================================

class ListItemSerializer(serializers.ModelSerializer):
    """Serializer for ListItem model with recursive children support."""
    created_by = UserMinimalSerializer(read_only=True)
    children = serializers.SerializerMethodField()
    full_path = serializers.ReadOnlyField(source='get_full_path')

    class Meta:
        model = ListItem
        fields = [
            'id', 'item_list', 'label', 'custom_id', 'parent', 'position',
            'is_active', 'custom_data', 'created_at', 'updated_at', 'created_by',
            'children', 'full_path'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_children(self, obj):
        """Recursively get all children of this item."""
        children = obj.children.filter(is_active=True)
        return ListItemSerializer(children, many=True, context=self.context).data

    def create(self, validated_data):
        # Set created_by from request context
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class ListItemMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for ListItem without children (to avoid deep recursion)."""
    full_path = serializers.ReadOnlyField(source='get_full_path')

    class Meta:
        model = ListItem
        fields = ['id', 'label', 'custom_id', 'parent', 'position', 'is_active', 'full_path']
        read_only_fields = fields


class ItemListSerializer(serializers.ModelSerializer):
    """Serializer for ItemList model."""
    created_by = UserMinimalSerializer(read_only=True)
    items = ListItemSerializer(many=True, read_only=True)
    items_count = serializers.SerializerMethodField()
    root_items = serializers.SerializerMethodField()

    class Meta:
        model = ItemList
        fields = [
            'id', 'title', 'description', 'is_active', 'custom_fields_schema',
            'created_at', 'updated_at', 'created_by',
            'items', 'items_count', 'root_items'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_items_count(self, obj):
        """Get the number of items in this list."""
        return obj.items.filter(is_active=True).count()

    def get_root_items(self, obj):
        """Get only root-level items (items without parents)."""
        root_items = obj.items.filter(parent__isnull=True, is_active=True)
        return ListItemSerializer(root_items, many=True, context=self.context).data

    def create(self, validated_data):
        # Set created_by from request context
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class ItemListMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for ItemList without nested items."""
    created_by = UserMinimalSerializer(read_only=True)
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = ItemList
        fields = [
            'id', 'title', 'description', 'is_active', 'custom_fields_schema',
            'created_at', 'updated_at', 'created_by', 'items_count'
        ]
        read_only_fields = fields

    def get_items_count(self, obj):
        """Get the number of items in this list."""
        return obj.items.filter(is_active=True).count()


class TicketFormSerializer(serializers.ModelSerializer):
    """Serializer for TicketForm model."""
    created_by = UserMinimalSerializer(read_only=True)
    item_lists = ItemListMinimalSerializer(many=True, read_only=True)
    item_list_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text='List of ItemList IDs to attach to this form'
    )
    submissions_count = serializers.SerializerMethodField()

    class Meta:
        model = TicketForm
        fields = [
            'id', 'title', 'description', 'item_lists', 'item_list_ids',
            'form_config', 'is_default', 'is_active',
            'created_at', 'updated_at', 'created_by', 'submissions_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_submissions_count(self, obj):
        """Get the number of submissions for this form."""
        return obj.submissions.count()

    def create(self, validated_data):
        item_list_ids = validated_data.pop('item_list_ids', [])
        validated_data['created_by'] = self.context['request'].user
        form = super().create(validated_data)

        if item_list_ids:
            form.item_lists.set(item_list_ids)

        return form

    def update(self, instance, validated_data):
        item_list_ids = validated_data.pop('item_list_ids', None)
        form = super().update(instance, validated_data)

        if item_list_ids is not None:
            form.item_lists.set(item_list_ids)

        return form


class TicketFormMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for TicketForm."""
    created_by = UserMinimalSerializer(read_only=True)

    class Meta:
        model = TicketForm
        fields = [
            'id', 'title', 'description', 'is_default', 'is_active',
            'created_at', 'created_by'
        ]
        read_only_fields = fields


class TicketFormSubmissionSerializer(serializers.ModelSerializer):
    """Serializer for TicketFormSubmission model."""
    submitted_by = UserMinimalSerializer(read_only=True)
    form = TicketFormMinimalSerializer(read_only=True)
    form_id = serializers.IntegerField(write_only=True)
    selected_items = ListItemMinimalSerializer(many=True, read_only=True)
    selected_item_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text='List of ListItem IDs selected in this submission'
    )
    ticket_data = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TicketFormSubmission
        fields = [
            'id', 'ticket', 'form', 'form_id', 'selected_items',
            'selected_item_ids', 'form_data', 'submitted_at', 'submitted_by',
            'ticket_data'
        ]
        read_only_fields = ['id', 'submitted_at', 'submitted_by']

    def get_ticket_data(self, obj):
        """Get minimal ticket data."""
        from .models import Ticket
        if obj.ticket:
            return {
                'id': obj.ticket.id,
                'title': obj.ticket.title,
                'status': obj.ticket.status
            }
        return None

    def create(self, validated_data):
        selected_item_ids = validated_data.pop('selected_item_ids', [])
        form_id = validated_data.pop('form_id')

        validated_data['submitted_by'] = self.context['request'].user
        validated_data['form_id'] = form_id

        submission = super().create(validated_data)

        if selected_item_ids:
            submission.selected_items.set(selected_item_ids)

        return submission

    def update(self, instance, validated_data):
        selected_item_ids = validated_data.pop('selected_item_ids', None)
        form_id = validated_data.pop('form_id', None)

        if form_id:
            validated_data['form_id'] = form_id

        submission = super().update(instance, validated_data)

        if selected_item_ids is not None:
            submission.selected_items.set(selected_item_ids)

        return submission
