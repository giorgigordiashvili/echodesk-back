from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group, Permission
from django.db import models
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType


class Department(models.Model):
    """Department model for organizing users"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name


class TenantGroup(models.Model):
    """Custom group model with feature-based access control"""
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)

    # Feature-based permissions - tied to tenant subscription
    features = models.ManyToManyField(
        'tenants.Feature',
        blank=True,
        related_name='groups',
        help_text="Features available to members of this group. Controls sidebar visibility and functionality access."
    )

    # Meta fields
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Group'
        verbose_name_plural = 'Groups'
        ordering = ['name']
    
    def __str__(self):
        return self.name

    def get_feature_keys(self):
        """Return a list of feature keys this group has access to"""
        return list(self.features.filter(is_active=True).values_list('key', flat=True))

    def has_feature(self, feature_key):
        """Check if this group has access to a specific feature"""
        return self.features.filter(key=feature_key, is_active=True).exists()


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('manager', 'Manager'),
        ('agent', 'Agent'),
        ('viewer', 'Viewer'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('pending', 'Pending Activation'),
    ]
    
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    
    # Enhanced user management fields
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='agent')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    primary_group = models.ForeignKey('TenantGroup', on_delete=models.SET_NULL, null=True, blank=True, related_name='primary_members', help_text='Primary group for this user')
    phone_number = models.CharField(max_length=20, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    department = models.ForeignKey('Department', on_delete=models.SET_NULL, null=True, blank=True, related_name='employees', help_text='Department this user belongs to')
    
    # Permission flags
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    # Tenant-specific permissions (individual user permissions)
    can_view_all_tickets = models.BooleanField(default=False)
    can_manage_users = models.BooleanField(default=False)
    can_make_calls = models.BooleanField(default=False)
    can_manage_groups = models.BooleanField(default=False)
    can_manage_settings = models.BooleanField(default=False)
    
    # Additional individual permissions
    can_create_tickets = models.BooleanField(default=True)
    can_edit_own_tickets = models.BooleanField(default=True)
    can_edit_all_tickets = models.BooleanField(default=False)
    can_delete_tickets = models.BooleanField(default=False)
    can_assign_tickets = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    can_export_data = models.BooleanField(default=False)
    can_manage_tags = models.BooleanField(default=False)
    can_manage_columns = models.BooleanField(default=False)
    can_view_boards = models.BooleanField(default=False)
    can_create_boards = models.BooleanField(default=False)
    can_edit_boards = models.BooleanField(default=False)
    can_delete_boards = models.BooleanField(default=False)
    can_access_orders = models.BooleanField(default=False)
    
    # Group membership
    tenant_groups = models.ManyToManyField(TenantGroup, blank=True, related_name='members')
    
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(blank=True, null=True)
    
    # Invitation tracking
    invited_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='invited_users')
    invitation_sent_at = models.DateTimeField(null=True, blank=True)
    
    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return self.email
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.email
    
    @property
    def is_admin(self):
        return self.role == 'admin' or self.is_superuser
    
    @property
    def is_manager(self):
        return self.role in ['admin', 'manager'] or self.is_superuser
    
    def has_permission(self, permission):
        """Check if user has specific tenant permission (individual or through group membership)"""
        if self.is_superuser:
            return True
        
        # Check individual permissions first
        individual_permissions = {
            'view_all_tickets': self.can_view_all_tickets,
            'manage_users': self.can_manage_users,
            'make_calls': self.can_make_calls,
            'manage_groups': self.can_manage_groups,
            'manage_settings': self.can_manage_settings,
            'create_tickets': self.can_create_tickets,
            'edit_own_tickets': self.can_edit_own_tickets,
            'edit_all_tickets': self.can_edit_all_tickets,
            'delete_tickets': self.can_delete_tickets,
            'assign_tickets': self.can_assign_tickets,
            'view_reports': self.can_view_reports,
            'export_data': self.can_export_data,
            'manage_tags': self.can_manage_tags,
            'manage_columns': self.can_manage_columns,
            'view_boards': self.can_view_boards,
            'create_boards': self.can_create_boards,
            'edit_boards': self.can_edit_boards,
            'delete_boards': self.can_delete_boards,
            'access_orders': self.can_access_orders,
        }
        
        # Check if user has individual permission
        if individual_permissions.get(permission, False):
            return True
        
        # Check role-based permissions (legacy support)
        role_permissions = {
            'view_all_tickets': self.is_manager,
            'manage_users': self.is_admin,
            'make_calls': self.is_manager,
            'manage_groups': self.is_admin,
            'manage_settings': self.is_admin,
            'edit_all_tickets': self.is_manager,
            'delete_tickets': self.is_manager,
            'assign_tickets': self.is_manager,
            'view_reports': self.is_manager,
            'export_data': self.is_manager,
            'manage_tags': self.is_manager,
            'manage_columns': self.is_manager,
            'view_boards': self.is_manager,  # Only managers/admins get full board access by role
            'create_boards': self.is_manager,
            'edit_boards': self.is_manager,
            'delete_boards': self.is_admin,
        }
        
        if role_permissions.get(permission, False):
            return True
        
        # Check group permissions
        for group in self.tenant_groups.filter(is_active=True):
            group_permission_field = f'can_{permission}'
            if hasattr(group, group_permission_field) and getattr(group, group_permission_field, False):
                return True
        
        return False
    
    def get_all_permissions(self):
        """Get all permissions this user has (individual + group + role-based)"""
        permissions = set()
        
        # Individual permissions
        permission_fields = [
            'view_all_tickets', 'manage_users', 'make_calls', 'manage_groups', 
            'manage_settings', 'create_tickets', 'edit_own_tickets', 
            'edit_all_tickets', 'delete_tickets', 'assign_tickets', 
            'view_reports', 'export_data', 'manage_tags', 'manage_columns',
            'view_boards', 'create_boards', 'edit_boards', 'delete_boards',
            'access_orders'
        ]
        
        for field in permission_fields:
            if self.has_permission(field):
                permissions.add(field)
        
        return list(permissions)
    
    def get_group_permissions(self):
        """Get feature keys inherited from groups"""
        group_features = set()

        for group in self.tenant_groups.filter(is_active=True):
            group_features.update(group.get_feature_keys())

        return list(group_features)

    def get_user_permissions_list(self):
        """Get user's direct individual permissions (not from groups)"""
        permissions = []
        permission_fields = [
            ('can_view_all_tickets', 'view_all_tickets'),
            ('can_manage_users', 'manage_users'),
            ('can_make_calls', 'make_calls'),
            ('can_manage_groups', 'manage_groups'),
            ('can_manage_settings', 'manage_settings'),
            ('can_create_tickets', 'create_tickets'),
            ('can_edit_own_tickets', 'edit_own_tickets'),
            ('can_edit_all_tickets', 'edit_all_tickets'),
            ('can_delete_tickets', 'delete_tickets'),
            ('can_assign_tickets', 'assign_tickets'),
            ('can_view_reports', 'view_reports'),
            ('can_export_data', 'export_data'),
            ('can_manage_tags', 'manage_tags'),
            ('can_manage_columns', 'manage_columns'),
            ('can_view_boards', 'view_boards'),
            ('can_create_boards', 'create_boards'),
            ('can_edit_boards', 'edit_boards'),
            ('can_delete_boards', 'delete_boards'),
            ('can_access_orders', 'access_orders'),
        ]
        
        for field_name, permission_name in permission_fields:
            if getattr(self, field_name, False):
                permissions.append(permission_name)
        
        return permissions

    def get_group_permissions_list(self):
        """Alias for get_group_permissions for consistency"""
        return self.get_group_permissions()

    def has_feature(self, feature_key):
        """
        Check if user has access to a specific feature

        Args:
            feature_key: The feature key string (e.g., 'ticket_management', 'whatsapp_integration')

        Returns:
            bool: True if user has access to the feature

        Logic:
            - Superadmins (is_staff=True or is_superuser=True) have access to ALL features
            - Regular users have access based on their group's features
        """
        # Superadmins have access to everything
        if self.is_staff or self.is_superuser:
            return True

        # Check if any of the user's groups have this feature
        return self.tenant_groups.filter(
            is_active=True,
            features__key=feature_key,
            features__is_active=True
        ).exists()

    def get_feature_keys(self):
        """
        Get all feature keys this user has access to

        Returns:
            list: List of feature keys the user can access
        """
        # Superadmins get all active features
        if self.is_staff or self.is_superuser:
            from tenants.feature_models import Feature
            return list(Feature.objects.filter(is_active=True).values_list('key', flat=True))

        # Get unique feature keys from all active groups
        feature_keys = set()
        for group in self.tenant_groups.filter(is_active=True):
            feature_keys.update(group.get_feature_keys())

        return list(feature_keys)

    def get_all_permissions_dict(self):
        """Get all permissions as a dictionary with categories"""
        individual_permissions = self.get_user_permissions_list()
        group_permissions = self.get_group_permissions()

        return {
            'individual': individual_permissions,
            'group': group_permissions,
            'all': list(set(individual_permissions + group_permissions))
        }


class Notification(models.Model):
    """
    Notification model for user notifications about ticket events
    """
    NOTIFICATION_TYPES = [
        ('ticket_assigned', 'Ticket Assigned'),
        ('ticket_mentioned', 'Mentioned in Ticket'),
        ('ticket_commented', 'Ticket Commented'),
        ('ticket_status_changed', 'Ticket Status Changed'),
        ('ticket_updated', 'Ticket Updated'),
        ('sub_ticket_created', 'Sub-ticket Created'),
        ('ticket_due_soon', 'Ticket Due Soon'),
    ]

    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='notifications',
        help_text='User who will receive this notification'
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPES,
        help_text='Type of notification'
    )
    title = models.CharField(
        max_length=255,
        help_text='Notification title/summary'
    )
    message = models.TextField(
        help_text='Detailed notification message'
    )

    # Link to related ticket
    ticket_id = models.IntegerField(
        null=True,
        blank=True,
        help_text='ID of related ticket'
    )

    # Additional metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text='Additional notification metadata (e.g., actor_name, old_value, new_value)'
    )

    # Notification state
    is_read = models.BooleanField(
        default=False,
        help_text='Whether the notification has been read'
    )
    read_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='When the notification was read'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='When the notification was created'
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['user', 'is_read']),
        ]

    def __str__(self):
        return f"{self.get_notification_type_display()} for {self.user.email}"

    def mark_as_read(self):
        """Mark this notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
