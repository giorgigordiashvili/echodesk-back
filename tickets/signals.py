"""
Signals for automatic notification creation on ticket events.
"""
from django.db.models.signals import post_save, pre_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import (
    Ticket,
    TicketComment,
    TicketAssignment,
)
import re
from asgiref.sync import async_to_sync
from django.db import connection

User = get_user_model()


def create_notification(user, notification_type, title, message, ticket_id=None, metadata=None):
    """
    Helper function to create notifications and broadcast them via WebSocket.
    """
    from users.models import Notification
    from users.consumers import send_notification_to_user

    if metadata is None:
        metadata = {}

    # Don't create duplicate notifications within 1 minute
    from django.utils import timezone
    from datetime import timedelta

    recent_notification = Notification.objects.filter(
        user=user,
        notification_type=notification_type,
        ticket_id=ticket_id,
        created_at__gte=timezone.now() - timedelta(minutes=1)
    ).first()

    if not recent_notification:
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            ticket_id=ticket_id,
            metadata=metadata
        )

        # Get updated unread count
        unread_count = Notification.objects.filter(
            user=user,
            is_read=False
        ).count()

        # Broadcast notification via WebSocket
        # Get tenant schema from current database connection
        tenant_schema = getattr(connection, 'schema_name', 'public')

        # Prepare notification data for WebSocket
        from django.utils.timesince import timesince
        notification_data = {
            'id': notification.id,
            'notification_type': notification.notification_type,
            'title': notification.title,
            'message': notification.message,
            'ticket_id': notification.ticket_id,
            'metadata': notification.metadata,
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat(),
            'read_at': notification.read_at.isoformat() if notification.read_at else None,
            'time_ago': timesince(notification.created_at),
            'user': notification.user.id,
            'user_name': notification.user.get_full_name() or notification.user.email,
        }

        # Send via WebSocket (async_to_sync to call async function from sync context)
        try:
            async_to_sync(send_notification_to_user)(
                tenant_schema=tenant_schema,
                user_id=user.id,
                notification_data=notification_data,
                unread_count=unread_count
            )
        except Exception as e:
            # Log error but don't fail the notification creation
            print(f"[Signals] Error broadcasting notification via WebSocket: {str(e)}")

        # Send Web Push notification (for when app is closed)
        try:
            from notifications.utils import send_notification_to_user as send_push

            # Build ticket URL if ticket_id exists
            ticket_url = f'/tickets/{ticket_id}' if ticket_id else '/'

            # Send push notification to all user's devices
            send_push(
                user=user,
                title=title,
                body=message,
                data={
                    'ticket_id': ticket_id,
                    'notification_type': notification_type,
                    'notification_id': notification.id,
                    'url': ticket_url
                },
                icon='/favicon.ico',
                url=ticket_url,
                tag=f'echodesk-{ticket_id or notification.id}'
            )
            print(f"[Signals] Web Push sent for notification {notification.id}")
        except Exception as e:
            # Log error but don't fail - Web Push is optional
            print(f"[Signals] Error sending Web Push notification: {str(e)}")


def extract_mentions(text):
    """
    Extract @mentions from text.
    Returns list of usernames mentioned.
    """
    # Match @username patterns (alphanumeric, dots, underscores, hyphens)
    pattern = r'@([\w\.\-]+)'
    mentions = re.findall(pattern, text)
    return mentions


def get_users_from_mentions(mentions):
    """
    Get User objects from list of mentioned usernames/emails.
    """
    users = []
    for mention in mentions:
        # Try to find by email first (most common)
        user = User.objects.filter(email__iexact=mention).first()
        if not user:
            # Try to find by first name or last name
            user = User.objects.filter(
                first_name__icontains=mention
            ).first() or User.objects.filter(
                last_name__icontains=mention
            ).first()
        if user:
            users.append(user)
    return users


@receiver(post_save, sender=TicketAssignment)
def notify_on_ticket_assignment(sender, instance, created, **kwargs):
    """
    Notify user when they are assigned to a ticket.
    """
    if created:
        ticket = instance.ticket
        assigned_user = instance.user
        assigned_by = instance.assigned_by

        # Don't notify if user assigned themselves
        if assigned_by and assigned_user.id == assigned_by.id:
            return

        assigner_name = assigned_by.get_full_name() if assigned_by else "Someone"

        create_notification(
            user=assigned_user,
            notification_type='ticket_assigned',
            title=f'Assigned to: {ticket.title}',
            message=f'{assigner_name} assigned you to this ticket as {instance.get_role_display()}',
            ticket_id=ticket.id,
            metadata={
                'role': instance.role,
                'assigned_by': assigned_by.email if assigned_by else None,
            }
        )


@receiver(post_save, sender=TicketComment)
def notify_on_ticket_comment(sender, instance, created, **kwargs):
    """
    Notify ticket participants when a comment is added.
    Also handles @mentions in comments.
    """
    if not created:
        return

    ticket = instance.ticket
    commenter = instance.user

    # Extract mentions from comment
    mentions = extract_mentions(instance.comment)
    mentioned_users = get_users_from_mentions(mentions)

    # Notify mentioned users
    for mentioned_user in mentioned_users:
        if mentioned_user.id != commenter.id:
            create_notification(
                user=mentioned_user,
                notification_type='ticket_mentioned',
                title=f'Mentioned in: {ticket.title}',
                message=f'{commenter.get_full_name()} mentioned you in a comment',
                ticket_id=ticket.id,
                metadata={
                    'comment_id': instance.id,
                    'commenter': commenter.email,
                }
            )

    # Notify ticket creator if they're not the commenter
    if ticket.created_by.id != commenter.id:
        create_notification(
            user=ticket.created_by,
            notification_type='ticket_commented',
            title=f'New comment on: {ticket.title}',
            message=f'{commenter.get_full_name()} added a comment',
            ticket_id=ticket.id,
            metadata={
                'comment_id': instance.id,
                'commenter': commenter.email,
            }
        )

    # Notify assigned users (excluding commenter and mentioned users)
    assigned_users = ticket.assigned_users.exclude(id=commenter.id)
    mentioned_user_ids = [u.id for u in mentioned_users]
    assigned_users = assigned_users.exclude(id__in=mentioned_user_ids)

    for assigned_user in assigned_users:
        create_notification(
            user=assigned_user,
            notification_type='ticket_commented',
            title=f'New comment on: {ticket.title}',
            message=f'{commenter.get_full_name()} added a comment',
            ticket_id=ticket.id,
            metadata={
                'comment_id': instance.id,
                'commenter': commenter.email,
            }
        )


@receiver(pre_save, sender=Ticket)
def track_ticket_status_change(sender, instance, **kwargs):
    """
    Track ticket status changes and notify assigned users.
    Uses pre_save to compare old and new column values.
    """
    if instance.pk:  # Only for existing tickets
        try:
            old_ticket = Ticket.objects.get(pk=instance.pk)

            # Check if column (status) changed
            if old_ticket.column_id != instance.column_id:
                instance._column_changed = True
                instance._old_column_name = old_ticket.column.name if old_ticket.column else 'None'
                instance._new_column_name = instance.column.name if instance.column else 'None'

            # Check if department changed
            if old_ticket.assigned_department_id != instance.assigned_department_id:
                instance._department_changed = True
                instance._old_department = old_ticket.assigned_department
                instance._new_department = instance.assigned_department
        except Ticket.DoesNotExist:
            pass


@receiver(post_save, sender=Ticket)
def notify_on_ticket_status_change(sender, instance, created, **kwargs):
    """
    Notify assigned users when ticket status (column) changes.
    """
    if created:
        return

    # Check if column was changed (set in pre_save)
    if getattr(instance, '_column_changed', False):
        old_column_name = getattr(instance, '_old_column_name', 'Unknown')
        new_column_name = getattr(instance, '_new_column_name', 'Unknown')

        # Notify all assigned users
        for assigned_user in instance.assigned_users.all():
            create_notification(
                user=assigned_user,
                notification_type='ticket_status_changed',
                title=f'Status changed: {instance.title}',
                message=f'Ticket status changed from "{old_column_name}" to "{new_column_name}"',
                ticket_id=instance.id,
                metadata={
                    'old_status': old_column_name,
                    'new_status': new_column_name,
                }
            )

        # Clean up temporary attributes
        delattr(instance, '_column_changed')
        delattr(instance, '_old_column_name')
        delattr(instance, '_new_column_name')

    # Check if department was changed (set in pre_save)
    if getattr(instance, '_department_changed', False):
        new_department = getattr(instance, '_new_department', None)
        old_department = getattr(instance, '_old_department', None)

        # Notify all users in the newly assigned department
        if new_department:
            department_users = new_department.employees.all()
            for user in department_users:
                create_notification(
                    user=user,
                    notification_type='ticket_assigned',
                    title=f'Department assigned: {instance.title}',
                    message=f'Ticket assigned to your department "{new_department.name}"',
                    ticket_id=instance.id,
                    metadata={
                        'department_id': new_department.id,
                        'department_name': new_department.name,
                        'old_department': old_department.name if old_department else None,
                    }
                )

        # Clean up temporary attributes
        delattr(instance, '_department_changed')
        delattr(instance, '_new_department')
        delattr(instance, '_old_department')


