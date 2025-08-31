from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Ticket, Tag, TicketComment, TicketColumn

User = get_user_model()


class TicketColumnSerializer(serializers.ModelSerializer):
    """Serializer for TicketColumn model."""
    created_by = serializers.StringRelatedField(read_only=True)
    tickets_count = serializers.SerializerMethodField()
    
    class Meta:
        model = TicketColumn
        fields = [
            'id', 'name', 'description', 'color', 'position', 
            'is_default', 'is_closed_status', 'created_at', 'updated_at',
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
        fields = ['name', 'description', 'color', 'position', 'is_default', 'is_closed_status']
        
    def create(self, validated_data):
        # Set created_by from request context
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


class TicketColumnUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating ticket columns."""
    
    class Meta:
        model = TicketColumn
        fields = ['name', 'description', 'color', 'position', 'is_default', 'is_closed_status']


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


class TicketSerializer(serializers.ModelSerializer):
    """Serializer for Ticket model."""
    created_by = UserMinimalSerializer(read_only=True)
    assigned_to = UserMinimalSerializer(read_only=True)
    assigned_to_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
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
    status = serializers.ReadOnlyField()  # Dynamic status from column
    is_closed = serializers.ReadOnlyField()  # Dynamic closed status from column
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'title', 'description', 'status', 'priority', 'is_closed',
            'column', 'column_id', 'position_in_column',
            'created_at', 'updated_at', 'created_by', 'assigned_to',
            'assigned_to_id', 'tags', 'tag_ids', 'comments', 'comments_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by', 'status', 'is_closed']

    def get_comments_count(self, obj):
        """Get the number of comments for this ticket."""
        return obj.comments.count()

    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        assigned_to_id = validated_data.pop('assigned_to_id', None)
        column_id = validated_data.pop('column_id', None)
        
        # Set created_by from request context
        validated_data['created_by'] = self.context['request'].user
        
        # Set assigned_to if provided
        if assigned_to_id:
            validated_data['assigned_to'] = User.objects.get(id=assigned_to_id)
        
        # Set column if provided
        if column_id:
            validated_data['column'] = TicketColumn.objects.get(id=column_id)
        
        ticket = Ticket.objects.create(**validated_data)
        
        # Set tags
        if tag_ids:
            ticket.tags.set(tag_ids)
        
        return ticket

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        assigned_to_id = validated_data.pop('assigned_to_id', None)
        column_id = validated_data.pop('column_id', None)
        
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
        
        return ticket


class TicketListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for ticket lists."""
    created_by = UserMinimalSerializer(read_only=True)
    assigned_to = UserMinimalSerializer(read_only=True)
    column = TicketColumnSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    status = serializers.ReadOnlyField()  # Dynamic status from column
    is_closed = serializers.ReadOnlyField()  # Dynamic closed status from column
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'title', 'status', 'priority', 'is_closed', 'column', 'position_in_column',
            'created_at', 'updated_at', 'created_by', 'assigned_to', 'tags', 'comments_count'
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
