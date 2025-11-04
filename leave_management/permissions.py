from rest_framework import permissions


class HasLeaveManagementFeature(permissions.BasePermission):
    """
    Permission check: Tenant has leave_management feature enabled
    """
    message = "Your organization does not have access to the Leave Management feature."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if tenant has the feature enabled
        if hasattr(request, 'tenant_has_feature'):
            return request.tenant_has_feature('leave_management')

        # Fallback to legacy feature check
        if hasattr(request.user, 'has_feature'):
            return request.user.has_feature('leave_management')

        return False


class IsLeaveEmployee(permissions.BasePermission):
    """
    Object-level permission: Employee can only access their own leave requests
    """
    message = "You can only access your own leave requests."

    def has_object_permission(self, request, view, obj):
        # Admins and staff have full access
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Check if the leave request belongs to the user
        return obj.employee == request.user


class IsLeaveManager(permissions.BasePermission):
    """
    Permission check: User is a manager (has direct reports)
    Object-level: Can access team members' leave requests
    """
    message = "You do not have manager permissions."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Admins and staff always have access
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Check if user has managed employees
        # This assumes User model has a 'managed_employees' related field
        # Adjust based on your actual user-manager relationship
        if hasattr(request.user, 'managed_employees'):
            return request.user.managed_employees.exists()

        # Check if user has manager permission
        if request.user.has_perm('leave_management.view_team_leaves'):
            return True

        return False

    def has_object_permission(self, request, view, obj):
        # Admins and staff have full access
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Check if the employee reports to this manager
        if hasattr(obj.employee, 'manager'):
            return obj.employee.manager == request.user

        return False


class CanApproveLeave(permissions.BasePermission):
    """
    Object-level permission: User can approve leave requests based on approval chain
    """
    message = "You do not have permission to approve this leave request."

    def has_object_permission(self, request, view, obj):
        from .utils import can_user_approve

        # Admins always have permission
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Check using utility function
        can_approve, reason = can_user_approve(request.user, obj)

        if not can_approve:
            self.message = reason

        return can_approve


class CanManageLeaveSettings(permissions.BasePermission):
    """
    Permission check: User can manage leave settings (admin only)
    """
    message = "Only administrators can manage leave settings."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Only staff and superusers can manage settings
        return request.user.is_staff or request.user.is_superuser


class CanManageLeaveTypes(permissions.BasePermission):
    """
    Permission check: User can manage leave types (admin only)
    """
    message = "Only administrators can manage leave types."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Only staff and superusers can manage leave types
        return request.user.is_staff or request.user.is_superuser


class CanManageLeaveBalances(permissions.BasePermission):
    """
    Permission check: User can manage leave balances (admin/HR only)
    """
    message = "Only administrators and HR can manage leave balances."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Staff and superusers have access
        if request.user.is_staff or request.user.is_superuser:
            return True

        # HR role has access
        if request.user.has_perm('leave_management.manage_balances'):
            return True

        return False


class CanViewTeamBalance(permissions.BasePermission):
    """
    Object-level permission: Manager can view their team's leave balances
    """
    message = "You can only view your team members' balances."

    def has_object_permission(self, request, view, obj):
        # Admins and staff have full access
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Employees can view their own balance
        if obj.user == request.user:
            return True

        # Managers can view their team's balances
        if hasattr(obj.user, 'manager'):
            return obj.user.manager == request.user

        return False


class CanManagePublicHolidays(permissions.BasePermission):
    """
    Permission check: User can manage public holidays (admin only)
    """
    message = "Only administrators can manage public holidays."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Only staff and superusers can manage holidays
        return request.user.is_staff or request.user.is_superuser


class CanCancelLeave(permissions.BasePermission):
    """
    Object-level permission: User can cancel a leave request
    """
    message = "You cannot cancel this leave request."

    def has_object_permission(self, request, view, obj):
        # Admins can cancel any leave
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Employees can cancel their own pending leaves
        if obj.employee == request.user and obj.status in ['pending', 'manager_approved', 'hr_approved']:
            return True

        # Managers can cancel their team's pending leaves
        if hasattr(obj.employee, 'manager') and obj.employee.manager == request.user:
            if obj.status in ['pending', 'manager_approved']:
                return True

        return False


class IsLeaveOwnerOrManager(permissions.BasePermission):
    """
    Object-level permission: User is the leave owner or their manager
    """
    message = "You can only access your own leaves or your team members' leaves."

    def has_object_permission(self, request, view, obj):
        # Admins and staff have full access
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Owner has access
        if obj.employee == request.user:
            return True

        # Manager has access to team member's leave
        if hasattr(obj.employee, 'manager'):
            return obj.employee.manager == request.user

        return False
