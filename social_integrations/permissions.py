"""
Custom permission classes for social media integrations
"""
from rest_framework import permissions


class CanManageSocialConnections(permissions.BasePermission):
    """
    Permission to manage social media connections (connect/disconnect pages)
    """
    message = "You do not have permission to manage social media connections."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Read-only permissions are allowed for viewing
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_permission('view_social_messages')

        # Write permissions require manage_social_connections
        return request.user.has_permission('manage_social_connections')


class CanViewSocialMessages(permissions.BasePermission):
    """
    Permission to view social media messages
    """
    message = "You do not have permission to view social media messages."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.has_permission('view_social_messages')


class CanSendSocialMessages(permissions.BasePermission):
    """
    Permission to send social media messages
    """
    message = "You do not have permission to send social media messages."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Read-only permissions
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_permission('view_social_messages')

        # Write permissions require send_social_messages
        return request.user.has_permission('send_social_messages')


class CanManageSocialSettings(permissions.BasePermission):
    """
    Permission to manage social media integration settings
    """
    message = "You do not have permission to manage social media settings."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.has_permission('manage_social_settings')
