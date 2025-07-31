from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Enhanced serializer for User model with full profile information"""
    full_name = serializers.ReadOnlyField(source='get_full_name')
    permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'status', 'department', 'phone_number', 'job_title',
            'can_view_all_tickets', 'can_manage_users', 'can_make_calls', 'can_manage_groups', 'can_manage_settings',
            'is_active', 'is_staff', 'date_joined', 'last_login',
            'invited_by', 'invitation_sent_at', 'permissions'
        ]
        read_only_fields = ['id', 'date_joined', 'invited_by', 'invitation_sent_at', 'last_login']
    
    def get_permissions(self, obj):
        return {
            'is_admin': obj.is_admin,
            'is_manager': obj.is_manager,
            'can_view_all_tickets': obj.has_permission('view_all_tickets'),
            'can_manage_users': obj.has_permission('manage_users'),
            'can_make_calls': obj.has_permission('make_calls'),
            'can_manage_groups': obj.has_permission('manage_groups'),
            'can_manage_settings': obj.has_permission('manage_settings'),
        }


class UserCreateSerializer(serializers.ModelSerializer):
    """Enhanced serializer for creating new users"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'password', 'password_confirm',
            'role', 'department', 'phone_number', 'job_title',
            'can_view_all_tickets', 'can_manage_users', 'can_make_calls', 'can_manage_groups', 'can_manage_settings'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def validate_role(self, value):
        # Only admins can create other admins
        request = self.context.get('request')
        if request and value == 'admin' and not request.user.is_admin:
            raise serializers.ValidationError("Only administrators can create admin users.")
        return value
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        
        user = User.objects.create_user(password=password, **validated_data)
        
        # Set invitation details
        request = self.context.get('request')
        if request:
            user.invited_by = request.user
            user.invitation_sent_at = timezone.now()
            user.save()
        
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user information"""
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'role', 'status', 'department', 
            'phone_number', 'job_title',
            'can_view_all_tickets', 'can_manage_users', 'can_make_calls', 'can_manage_groups', 'can_manage_settings',
            'is_active'
        ]
    
    def validate_role(self, value):
        request = self.context.get('request')
        if request and value == 'admin' and not request.user.is_admin:
            raise serializers.ValidationError("Only administrators can assign admin role.")
        return value


class BulkUserActionSerializer(serializers.Serializer):
    """Serializer for bulk user actions"""
    ACTION_CHOICES = [
        ('activate', 'Activate Users'),
        ('deactivate', 'Deactivate Users'),
        ('delete', 'Delete Users'),
        ('change_role', 'Change Role'),
        ('change_status', 'Change Status'),
    ]
    
    user_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, required=False)
    status = serializers.ChoiceField(choices=User.STATUS_CHOICES, required=False)
    
    def validate(self, data):
        action = data['action']
        
        if action == 'change_role' and not data.get('role'):
            raise serializers.ValidationError("role is required for change_role action")
        
        if action == 'change_status' and not data.get('status'):
            raise serializers.ValidationError("status is required for change_status action")
        
        return data


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)
    
    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Invalid old password")
        return value


class GroupSerializer(serializers.ModelSerializer):
    """Serializer for Django Group model"""
    user_count = serializers.SerializerMethodField()
    users = serializers.StringRelatedField(source='user_set', many=True, read_only=True)
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'user_count', 'users']
    
    def get_user_count(self, obj):
        return obj.user_set.count()


class GroupCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating groups"""
    class Meta:
        model = Group
        fields = ['name']
    
    def validate_name(self, value):
        if Group.objects.filter(name=value).exists():
            raise serializers.ValidationError("A group with this name already exists.")
        return value


class GroupUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating groups"""
    class Meta:
        model = Group
        fields = ['name']
    
    def validate_name(self, value):
        # Allow the same name if it's the current object
        if self.instance and self.instance.name == value:
            return value
        if Group.objects.filter(name=value).exists():
            raise serializers.ValidationError("A group with this name already exists.")
        return value
