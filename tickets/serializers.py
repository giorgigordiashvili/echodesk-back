from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Ticket, Tag, TicketComment, TicketColumn, SubTicket, ChecklistItem,
    TicketAssignment, SubTicketAssignment, TicketTimeLog, Board
)

User = get_user_model()


class BoardSerializer(serializers.ModelSerializer):
    """Serializer for Board model."""
    created_by = serializers.StringRelatedField(read_only=True)
    columns_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Board
        fields = [
            'id', 'name', 'description', 'is_default',
            'created_at', 'updated_at', 'created_by', 'columns_count'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']
    
    def get_columns_count(self, obj):
        return obj.columns.count()


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


class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal user serializer for ticket relationships."""
    
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']
        read_only_fields = ['id', 'email', 'first_name', 'last_name']


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
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'title', 'description', 'rich_description', 'description_format',
            'status', 'priority', 'is_closed', 'is_order', 'column', 'column_id', 'position_in_column',
            'created_at', 'updated_at', 'created_by', 'assigned_to', 'assigned_to_id',
            'assigned_users', 'assignments', 'assigned_user_ids', 'assignment_roles',
            'tags', 'tag_ids', 'comments', 'comments_count',
            'sub_tickets', 'sub_tickets_count', 'completed_sub_tickets_count',
            'checklist_items', 'checklist_items_count', 'completed_checklist_items_count'
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
