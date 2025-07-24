from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Ticket, Tag, TicketComment

User = get_user_model()


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
        fields = ['id', 'username', 'first_name', 'last_name', 'email']
        read_only_fields = ['id', 'username', 'first_name', 'last_name', 'email']


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
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True
    )
    comments = TicketCommentSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'title', 'description', 'status', 'priority',
            'created_at', 'updated_at', 'created_by', 'assigned_to',
            'assigned_to_id', 'tags', 'tag_ids', 'comments', 'comments_count'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

    def get_comments_count(self, obj):
        """Get the number of comments for this ticket."""
        return obj.comments.count()

    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        assigned_to_id = validated_data.pop('assigned_to_id', None)
        
        # Set created_by from request context
        validated_data['created_by'] = self.context['request'].user
        
        # Set assigned_to if provided
        if assigned_to_id:
            validated_data['assigned_to'] = User.objects.get(id=assigned_to_id)
        
        ticket = Ticket.objects.create(**validated_data)
        
        # Set tags
        if tag_ids:
            ticket.tags.set(tag_ids)
        
        return ticket

    def update(self, instance, validated_data):
        tag_ids = validated_data.pop('tag_ids', None)
        assigned_to_id = validated_data.pop('assigned_to_id', None)
        
        # Handle assigned_to field
        if assigned_to_id is not None:
            if assigned_to_id:
                validated_data['assigned_to'] = User.objects.get(id=assigned_to_id)
            else:
                validated_data['assigned_to'] = None
        
        ticket = super().update(instance, validated_data)
        
        # Update tags if provided
        if tag_ids is not None:
            ticket.tags.set(tag_ids)
        
        return ticket


class TicketListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for ticket lists."""
    created_by = UserMinimalSerializer(read_only=True)
    assigned_to = UserMinimalSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'title', 'status', 'priority', 'created_at', 'updated_at',
            'created_by', 'assigned_to', 'tags', 'comments_count'
        ]
        read_only_fields = fields

    def get_comments_count(self, obj):
        """Get the number of comments for this ticket."""
        return obj.comments.count()
