from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

User = get_user_model()


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Django permissions"""
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'content_type']


class GroupSerializer(serializers.ModelSerializer):
    """Serializer for Django Groups with permissions"""
    permissions = PermissionSerializer(many=True, read_only=True)
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of permission IDs to assign to this group"
    )
    user_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions', 'permission_ids', 'user_count']
    
    def get_user_count(self, obj):
        return obj.user_set.count()
    
    def create(self, validated_data):
        permission_ids = validated_data.pop('permission_ids', [])
        group = Group.objects.create(**validated_data)
        
        if permission_ids:
            permissions = Permission.objects.filter(id__in=permission_ids)
            group.permissions.set(permissions)
        
        return group
    
    def update(self, instance, validated_data):
        permission_ids = validated_data.pop('permission_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if permission_ids is not None:
            permissions = Permission.objects.filter(id__in=permission_ids)
            instance.permissions.set(permissions)
        
        return instance


class GroupCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating groups"""
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of permission IDs to assign to this group"
    )
    
    class Meta:
        model = Group
        fields = ['name', 'permission_ids']
    
    def create(self, validated_data):
        permission_ids = validated_data.pop('permission_ids', [])
        group = Group.objects.create(**validated_data)
        
        if permission_ids:
            permissions = Permission.objects.filter(id__in=permission_ids)
            group.permissions.set(permissions)
        
        return group


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model with permissions and groups"""
    full_name = serializers.ReadOnlyField()
    permissions = serializers.SerializerMethodField()
    group_permissions = serializers.SerializerMethodField()
    all_permissions = serializers.SerializerMethodField()
    groups = GroupSerializer(many=True, read_only=True)
    group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of group IDs to assign to this user"
    )
    user_permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of permission IDs to assign directly to this user"
    )
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'status', 'phone_number', 'job_title',
            'is_active', 'is_staff', 'date_joined', 'last_login',
            'permissions', 'group_permissions', 'all_permissions',
            'groups', 'group_ids', 'user_permission_ids'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login']
    
    def get_permissions(self, obj):
        """Get user's direct permissions"""
        return obj.get_user_permissions_list()
    
    def get_group_permissions(self, obj):
        """Get permissions from groups"""
        return obj.get_group_permissions_list()
    
    def get_all_permissions(self, obj):
        """Get all permissions (user + group) as a dictionary"""
        return obj.get_all_permissions_dict()
    
    def update(self, instance, validated_data):
        group_ids = validated_data.pop('group_ids', None)
        user_permission_ids = validated_data.pop('user_permission_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if group_ids is not None:
            groups = Group.objects.filter(id__in=group_ids)
            instance.groups.set(groups)
        
        if user_permission_ids is not None:
            permissions = Permission.objects.filter(id__in=user_permission_ids)
            instance.user_permissions.set(permissions)
        
        return instance


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating users"""
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of group IDs to assign to this user"
    )
    user_permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of permission IDs to assign directly to this user"
    )
    
    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'password', 'password_confirm',
            'role', 'status', 'phone_number', 'job_title',
            'group_ids', 'user_permission_ids'
        ]
    
    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match")
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('password_confirm')
        group_ids = validated_data.pop('group_ids', [])
        user_permission_ids = validated_data.pop('user_permission_ids', [])
        password = validated_data.pop('password')
        
        user = User.objects.create_user(password=password, **validated_data)
        
        if group_ids:
            groups = Group.objects.filter(id__in=group_ids)
            user.groups.set(groups)
        
        if user_permission_ids:
            permissions = Permission.objects.filter(id__in=user_permission_ids)
            user.user_permissions.set(permissions)
        
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating users"""
    group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of group IDs to assign to this user"
    )
    user_permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of permission IDs to assign directly to this user"
    )
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'role', 'status', 
            'phone_number', 'job_title', 'is_active',
            'group_ids', 'user_permission_ids'
        ]
    
    def update(self, instance, validated_data):
        group_ids = validated_data.pop('group_ids', None)
        user_permission_ids = validated_data.pop('user_permission_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if group_ids is not None:
            groups = Group.objects.filter(id__in=group_ids)
            instance.groups.set(groups)
        
        if user_permission_ids is not None:
            permissions = Permission.objects.filter(id__in=user_permission_ids)
            instance.user_permissions.set(permissions)
        
        return instance


class BulkUserActionSerializer(serializers.Serializer):
    """Serializer for bulk user actions"""
    user_ids = serializers.ListField(child=serializers.IntegerField())
    action = serializers.ChoiceField(choices=[
        ('activate', 'Activate'),
        ('deactivate', 'Deactivate'),
        ('delete', 'Delete'),
        ('change_role', 'Change Role'),
        ('add_to_group', 'Add to Group'),
        ('remove_from_group', 'Remove from Group'),
    ])
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, required=False)
    group_id = serializers.IntegerField(required=False)


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
            raise serializers.ValidationError("Old password is incorrect")
        return value


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    email = serializers.EmailField()
    password = serializers.CharField()
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(email=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid email or password.')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled.')
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Must include email and password.')
