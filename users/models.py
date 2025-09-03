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
    """Custom group model with permissions for tenant-specific access control"""
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    
    # Group-level permissions
    can_view_all_tickets = models.BooleanField(default=False, help_text="Members can view all tickets in the tenant")
    can_manage_users = models.BooleanField(default=False, help_text="Members can manage user accounts")
    can_make_calls = models.BooleanField(default=False, help_text="Members can make phone calls")
    can_manage_groups = models.BooleanField(default=False, help_text="Members can manage groups")
    can_manage_settings = models.BooleanField(default=False, help_text="Members can manage tenant settings")
    
    # Additional group permissions
    can_create_tickets = models.BooleanField(default=True, help_text="Members can create new tickets")
    can_edit_own_tickets = models.BooleanField(default=True, help_text="Members can edit their own tickets")
    can_edit_all_tickets = models.BooleanField(default=False, help_text="Members can edit any ticket")
    can_delete_tickets = models.BooleanField(default=False, help_text="Members can delete tickets")
    can_assign_tickets = models.BooleanField(default=False, help_text="Members can assign tickets to others")
    can_view_reports = models.BooleanField(default=False, help_text="Members can view analytics and reports")
    can_export_data = models.BooleanField(default=False, help_text="Members can export data")
    can_manage_tags = models.BooleanField(default=False, help_text="Members can manage ticket tags")
    can_manage_columns = models.BooleanField(default=False, help_text="Members can manage kanban board columns")
    can_view_boards = models.BooleanField(default=True, help_text="Members can view and access kanban boards")
    can_create_boards = models.BooleanField(default=False, help_text="Members can create new kanban boards")
    can_edit_boards = models.BooleanField(default=False, help_text="Members can edit kanban board details")
    can_delete_boards = models.BooleanField(default=False, help_text="Members can delete kanban boards")
    can_access_orders = models.BooleanField(default=False, help_text="Members can access order management functionality")
    
    # Meta permissions
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Group'
        verbose_name_plural = 'Groups'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_permissions_list(self):
        """Return a list of permissions this group has"""
        permissions = []
        permission_fields = [
            'can_view_all_tickets', 'can_manage_users', 'can_make_calls', 
            'can_manage_groups', 'can_manage_settings', 'can_create_tickets',
            'can_edit_own_tickets', 'can_edit_all_tickets', 'can_delete_tickets',
            'can_assign_tickets', 'can_view_reports', 'can_export_data',
            'can_manage_tags', 'can_manage_columns', 'can_view_boards',
            'can_create_boards', 'can_edit_boards', 'can_delete_boards',
            'can_access_orders'
        ]
        
        for field in permission_fields:
            if getattr(self, field, False):
                permissions.append(field)
        
        return permissions


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
        """Get permissions inherited from groups"""
        group_permissions = set()
        
        for group in self.tenant_groups.filter(is_active=True):
            group_permissions.update(group.get_permissions_list())
        
        return list(group_permissions)

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
        ]
        
        for field_name, permission_name in permission_fields:
            if getattr(self, field_name, False):
                permissions.append(permission_name)
        
        return permissions

    def get_group_permissions_list(self):
        """Alias for get_group_permissions for consistency"""
        return self.get_group_permissions()

    def get_all_permissions_dict(self):
        """Get all permissions as a dictionary with categories"""
        individual_permissions = self.get_user_permissions_list()
        group_permissions = self.get_group_permissions()
        
        return {
            'individual': individual_permissions,
            'group': group_permissions,
            'all': list(set(individual_permissions + group_permissions))
        }
