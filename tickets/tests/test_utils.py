"""
Test utilities and fixtures for tickets tests.
Provides helper functions for creating test data.
"""
from django.contrib.auth import get_user_model
from tickets.models import (
    Board, TicketColumn, Tag, Ticket, SubTicket,
    ChecklistItem, TicketComment, TicketTimeLog,
    TicketPayment, TicketAssignment, SubTicketAssignment,
    ItemList, ListItem, TicketForm, TicketFormSubmission,
    TicketAttachment, TicketHistory
)
from users.models import TenantGroup, Department
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import uuid

User = get_user_model()


class TestDataMixin:
    """Mixin providing test data creation methods."""

    _user_counter = 0

    @classmethod
    def create_test_user(cls, email=None, password='testpass123', **kwargs):
        """Create a test user with unique email."""
        if email is None:
            cls._user_counter += 1
            email = f'test{cls._user_counter}@example.com'

        # Check if user already exists
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            return existing_user

        defaults = {
            'first_name': 'Test',
            'last_name': 'User',
            'is_active': True,
        }
        defaults.update(kwargs)

        user = User.objects.create_user(
            email=email,
            password=password,
            **defaults
        )
        return user

    @staticmethod
    def create_test_group(name='Test Group', **kwargs):
        """Create a test tenant group."""
        defaults = {
            'description': 'Test group for testing',
        }
        defaults.update(kwargs)

        group = TenantGroup.objects.create(
            name=name,
            **defaults
        )
        return group

    @staticmethod
    def create_test_department(name='Test Department', **kwargs):
        """Create a test department."""
        defaults = {
            'description': 'Test department',
        }
        defaults.update(kwargs)

        department = Department.objects.create(
            name=name,
            **defaults
        )
        return department

    @classmethod
    def create_test_board(cls, name='Test Board', created_by=None, **kwargs):
        """Create a test board."""
        if not created_by:
            created_by = cls.create_test_user()

        defaults = {
            'description': 'Test board for testing',
            'is_default': False,
        }
        defaults.update(kwargs)

        board = Board.objects.create(
            name=name,
            created_by=created_by,
            **defaults
        )
        return board

    @classmethod
    def create_test_column(cls, name='To Do', board=None, created_by=None, **kwargs):
        """Create a test ticket column."""
        if not board:
            board = cls.create_test_board()
        if not created_by:
            created_by = board.created_by

        defaults = {
            'description': 'Test column',
            'color': '#6B7280',
            'position': 0,
            'is_default': False,
            'is_closed_status': False,
            'track_time': False,
        }
        defaults.update(kwargs)

        column = TicketColumn.objects.create(
            name=name,
            board=board,
            created_by=created_by,
            **defaults
        )
        return column

    @classmethod
    def create_test_tag(cls, name='Test Tag', created_by=None, **kwargs):
        """Create a test tag."""
        if not created_by:
            created_by = cls.create_test_user()

        defaults = {
            'color': '#3B82F6',
            'description': 'Test tag for testing',
        }
        defaults.update(kwargs)

        tag = Tag.objects.create(
            name=name,
            created_by=created_by,
            **defaults
        )
        return tag

    @classmethod
    def create_test_ticket(cls, title='Test Ticket', created_by=None, column=None, **kwargs):
        """Create a test ticket."""
        if not created_by:
            created_by = cls.create_test_user()
        if not column:
            column = cls.create_test_column()

        defaults = {
            'description': 'Test ticket description',
            'priority': 'medium',
            'is_order': False,
        }
        defaults.update(kwargs)

        ticket = Ticket.objects.create(
            title=title,
            created_by=created_by,
            column=column,
            **defaults
        )
        return ticket

    @classmethod
    def create_test_sub_ticket(cls, title='Test SubTicket', parent_ticket=None, created_by=None, **kwargs):
        """Create a test sub-ticket."""
        if not parent_ticket:
            parent_ticket = cls.create_test_ticket()
        if not created_by:
            created_by = parent_ticket.created_by

        defaults = {
            'description': 'Test sub-ticket description',
            'priority': 'medium',
            'is_completed': False,
        }
        defaults.update(kwargs)

        sub_ticket = SubTicket.objects.create(
            title=title,
            parent_ticket=parent_ticket,
            created_by=created_by,
            **defaults
        )
        return sub_ticket

    @classmethod
    def create_test_checklist_item(cls, text='Test checklist item', ticket=None, created_by=None, **kwargs):
        """Create a test checklist item."""
        if not ticket:
            ticket = cls.create_test_ticket()
        if not created_by:
            created_by = ticket.created_by

        defaults = {
            'is_checked': False,
            'position': 0,
        }
        defaults.update(kwargs)

        item = ChecklistItem.objects.create(
            text=text,
            ticket=ticket,
            created_by=created_by,
            **defaults
        )
        return item

    @classmethod
    def create_test_comment(cls, comment='Test comment', ticket=None, user=None, **kwargs):
        """Create a test comment."""
        if not ticket:
            ticket = cls.create_test_ticket()
        if not user:
            user = ticket.created_by

        comment_obj = TicketComment.objects.create(
            comment=comment,
            ticket=ticket,
            user=user,
            **kwargs
        )
        return comment_obj

    @classmethod
    def create_test_time_log(cls, ticket=None, column=None, user=None, **kwargs):
        """Create a test time log."""
        if not ticket:
            ticket = cls.create_test_ticket()
        if not column:
            column = ticket.column
        if not user:
            user = ticket.created_by

        defaults = {}
        defaults.update(kwargs)

        time_log = TicketTimeLog.objects.create(
            ticket=ticket,
            column=column,
            user=user,
            **defaults
        )
        return time_log

    @classmethod
    def create_test_payment(cls, ticket=None, amount=100.00, user=None, **kwargs):
        """Create a test payment."""
        if not ticket:
            ticket = cls.create_test_ticket(price=Decimal('200.00'))
        if not user:
            user = ticket.created_by

        defaults = {
            'currency': 'USD',
            'payment_method': 'manual',
            'processed_by': user,
        }
        defaults.update(kwargs)

        payment = TicketPayment.objects.create(
            ticket=ticket,
            amount=Decimal(str(amount)),
            **defaults
        )
        return payment

    @classmethod
    def create_test_item_list(cls, title='Test List', **kwargs):
        """Create a test item list."""
        defaults = {
            'description': 'Test list for testing',
            'is_active': True,
        }
        defaults.update(kwargs)

        item_list = ItemList.objects.create(
            title=title,
            **defaults
        )
        return item_list
