"""
Custom permission classes for social media integrations
"""
from rest_framework import permissions


class CanManageSocialConnections(permissions.BasePermission):
    """
    Permission to manage social media connections (connect/disconnect pages)

    - Read access (GET): Users with social_integrations feature
    - Write access (POST/PUT/DELETE): Admins only or users with manage_social_connections permission
    """
    message = "You do not have permission to manage social media connections."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Read-only permissions: Check if user has social_integrations feature
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_feature('social_integrations')

        # Write permissions require admin role or explicit permission
        return (
            request.user.role == 'admin' or
            request.user.has_permission('manage_social_connections')
        )


class CanViewSocialMessages(permissions.BasePermission):
    """
    Permission to view social media messages

    - Users with social_integrations feature can view messages
    """
    message = "You do not have permission to view social media messages."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has social_integrations feature through their group
        return request.user.has_feature('social_integrations')


class CanSendSocialMessages(permissions.BasePermission):
    """
    Permission to send social media messages

    - Users with social_integrations feature can send messages
    """
    message = "You do not have permission to send social media messages."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # All users with social_integrations feature can send messages
        return request.user.has_feature('social_integrations')


class CanManageSocialSettings(permissions.BasePermission):
    """
    Permission to manage social media integration settings

    - Only admins or users with explicit permission can manage settings
    """
    message = "You do not have permission to manage social media settings."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Only admins or users with explicit permission
        return (
            request.user.role == 'admin' or
            request.user.has_permission('manage_social_settings')
        )


class IsSuperAdmin(permissions.BasePermission):
    """
    Permission that only allows superadmins (is_superuser=True)
    """
    message = "This action is restricted to superadmins only."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.is_superuser
