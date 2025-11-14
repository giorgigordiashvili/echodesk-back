"""
Custom permission classes for invoice management
"""
from rest_framework import permissions


class CanManageInvoices(permissions.BasePermission):
    """
    Permission to manage invoices

    - Users with invoice_management feature can access invoice endpoints
    """
    message = "Your subscription does not include access to invoice management."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has invoice_management feature through their subscription
        return request.user.has_feature('invoice_management')


class CanViewInvoices(permissions.BasePermission):
    """
    Permission to view invoices

    - Users with invoice_management feature can view invoices
    """
    message = "You do not have permission to view invoices."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # Check if user has invoice_management feature
        return request.user.has_feature('invoice_management')
