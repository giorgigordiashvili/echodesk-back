"""
Test cases for tickets models.
Tests model creation, validation, properties, and methods.
"""
from django.test import TestCase
from django.utils import timezone
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import timedelta, date
from tickets.tests.test_utils import TestDataMixin
from tickets.models import (
    Board, TicketColumn, Tag, Ticket,
    ChecklistItem, TicketComment, TicketTimeLog,
    TicketPayment
)


class BoardModelTest(TestCase, TestDataMixin):
    """Test the Board model."""

    def test_create_board(self):
        """Test creating a board."""
        board = self.create_test_board(name='Project Board')
        self.assertEqual(board.name, 'Project Board')
        self.assertIsNotNone(board.created_by)
        self.assertFalse(board.is_default)

    def test_board_string_representation(self):
        """Test board __str__ method."""
        board = self.create_test_board(name='Support Board')
        self.assertEqual(str(board), 'Support Board')

    def test_only_one_default_board(self):
        """Test that only one board can be default."""
        board1 = self.create_test_board(name='Board 1', is_default=True)
        self.assertTrue(board1.is_default)

        board2 = self.create_test_board(name='Board 2', is_default=True)
        self.assertTrue(board2.is_default)

        # Refresh board1 from database
        board1.refresh_from_db()
        self.assertFalse(board1.is_default)

    def test_board_payment_summary(self):
        """Test board payment summary calculation."""
        board = self.create_test_board()
        column = self.create_test_column(board=board)

        # Create tickets with different payment statuses
        ticket1 = self.create_test_ticket(
            column=column,
            price=Decimal('100.00'),
            amount_paid=Decimal('100.00'),
            is_paid=True
        )
        ticket2 = self.create_test_ticket(
            column=column,
            price=Decimal('200.00'),
            amount_paid=Decimal('50.00'),
            is_paid=False
        )

        summary = board.get_payment_summary()
        self.assertEqual(summary['total_tickets'], 2)
        self.assertEqual(summary['total_price'], Decimal('300.00'))
        self.assertEqual(summary['total_paid'], Decimal('150.00'))
        self.assertEqual(summary['remaining_balance'], Decimal('150.00'))


class TicketColumnModelTest(TestCase, TestDataMixin):
    """Test the TicketColumn model."""

    def test_create_column(self):
        """Test creating a ticket column."""
        column = self.create_test_column(name='In Progress')
        self.assertEqual(column.name, 'In Progress')
        self.assertIsNotNone(column.board)
        self.assertEqual(column.color, '#6B7280')

    def test_column_string_representation(self):
        """Test column __str__ method."""
        column = self.create_test_column(name='Done')
        self.assertEqual(str(column), 'Done')

    def test_only_one_default_column_per_board(self):
        """Test that only one column per board can be default."""
        board = self.create_test_board()
        col1 = self.create_test_column(name='Col 1', board=board, is_default=True)
        self.assertTrue(col1.is_default)

        col2 = self.create_test_column(name='Col 2', board=board, is_default=True)
        self.assertTrue(col2.is_default)

        # Refresh col1
        col1.refresh_from_db()
        self.assertFalse(col1.is_default)

    def test_unique_column_name_per_board(self):
        """Test that column names must be unique per board."""
        board = self.create_test_board()
        self.create_test_column(name='To Do', board=board)

        # Creating another column with same name on same board should fail
        with self.assertRaises(IntegrityError):
            self.create_test_column(name='To Do', board=board)

    def test_column_ordering(self):
        """Test that columns are ordered by position."""
        board = self.create_test_board()
        col1 = self.create_test_column(name='Col 1', board=board, position=2)
        col2 = self.create_test_column(name='Col 2', board=board, position=0)
        col3 = self.create_test_column(name='Col 3', board=board, position=1)

        columns = list(TicketColumn.objects.filter(board=board))
        self.assertEqual(columns[0], col2)
        self.assertEqual(columns[1], col3)
        self.assertEqual(columns[2], col1)


class TagModelTest(TestCase, TestDataMixin):
    """Test the Tag model."""

    def test_create_tag(self):
        """Test creating a tag."""
        tag = self.create_test_tag(name='Bug')
        self.assertEqual(tag.name, 'Bug')
        self.assertEqual(tag.color, '#3B82F6')

    def test_tag_string_representation(self):
        """Test tag __str__ method."""
        tag = self.create_test_tag(name='Feature')
        self.assertEqual(str(tag), 'Feature')

    def test_tag_unique_name(self):
        """Test that tag names must be unique."""
        self.create_test_tag(name='Priority')

        # Creating another tag with same name should fail
        with self.assertRaises(IntegrityError):
            self.create_test_tag(name='Priority')


class TicketModelTest(TestCase, TestDataMixin):
    """Test the Ticket model."""

    def test_create_ticket(self):
        """Test creating a ticket."""
        ticket = self.create_test_ticket(title='Fix login bug')
        self.assertEqual(ticket.title, 'Fix login bug')
        self.assertEqual(ticket.priority, 'medium')
        self.assertIsNotNone(ticket.column)
        self.assertIsNotNone(ticket.created_by)

    def test_ticket_string_representation(self):
        """Test ticket __str__ method."""
        ticket = self.create_test_ticket(title='Add new feature')
        self.assertEqual(str(ticket), 'Add new feature')

    def test_ticket_status_property(self):
        """Test ticket status property from column."""
        column = self.create_test_column(name='In Progress')
        ticket = self.create_test_ticket(column=column)
        self.assertEqual(ticket.status, 'in_progress')

    def test_ticket_is_closed_property(self):
        """Test ticket is_closed property."""
        column = self.create_test_column(name='Done', is_closed_status=True)
        ticket = self.create_test_ticket(column=column)
        self.assertTrue(ticket.is_closed)

    def test_ticket_auto_assigns_to_default_column(self):
        """Test that tickets auto-assign to default column."""
        board = self.create_test_board()
        default_column = self.create_test_column(
            name='Backlog',
            board=board,
            is_default=True
        )

        # Create ticket without specifying column
        ticket = Ticket.objects.create(
            title='Test Ticket',
            created_by=default_column.created_by
        )

        self.assertEqual(ticket.column, default_column)

    def test_ticket_position_auto_increment(self):
        """Test that ticket positions auto-increment within column."""
        column = self.create_test_column()
        ticket1 = self.create_test_ticket(column=column)
        ticket2 = self.create_test_ticket(column=column)

        # ticket2 should have position greater than ticket1
        self.assertGreater(ticket2.position_in_column, ticket1.position_in_column)

    def test_ticket_payment_status_no_payment(self):
        """Test payment status when no payment required."""
        ticket = self.create_test_ticket()
        self.assertEqual(ticket.payment_status, 'no_payment_required')

    def test_ticket_payment_status_paid(self):
        """Test payment status when fully paid."""
        ticket = self.create_test_ticket(
            price=Decimal('100.00'),
            amount_paid=Decimal('100.00'),
            is_paid=True
        )
        self.assertEqual(ticket.payment_status, 'paid')

    def test_ticket_payment_status_unpaid(self):
        """Test payment status when unpaid."""
        ticket = self.create_test_ticket(
            price=Decimal('100.00'),
            amount_paid=Decimal('0.00'),
            is_paid=False
        )
        self.assertEqual(ticket.payment_status, 'unpaid')

    def test_ticket_payment_status_partially_paid(self):
        """Test payment status when partially paid."""
        ticket = self.create_test_ticket(
            price=Decimal('100.00'),
            amount_paid=Decimal('50.00'),
            is_paid=False
        )
        self.assertEqual(ticket.payment_status, 'partially_paid')

    def test_ticket_remaining_balance(self):
        """Test remaining balance calculation."""
        ticket = self.create_test_ticket(
            price=Decimal('100.00'),
            amount_paid=Decimal('30.00')
        )
        self.assertEqual(ticket.remaining_balance, Decimal('70.00'))

    def test_ticket_is_overdue(self):
        """Test is_overdue property."""
        yesterday = (timezone.now() - timedelta(days=1)).date()
        ticket = self.create_test_ticket(
            price=Decimal('100.00'),
            payment_due_date=yesterday,
            is_paid=False
        )
        self.assertTrue(ticket.is_overdue)

    def test_ticket_add_payment(self):
        """Test adding payment to ticket."""
        ticket = self.create_test_ticket(
            price=Decimal('100.00'),
            amount_paid=Decimal('0.00')
        )

        remaining = ticket.add_payment(Decimal('50.00'))
        self.assertEqual(ticket.amount_paid, Decimal('50.00'))
        self.assertEqual(remaining, Decimal('50.00'))
        self.assertFalse(ticket.is_paid)

    def test_ticket_add_payment_marks_as_paid(self):
        """Test that adding payment auto-marks as paid when full."""
        ticket = self.create_test_ticket(
            price=Decimal('100.00'),
            amount_paid=Decimal('0.00')
        )

        ticket.add_payment(Decimal('100.00'))
        self.assertEqual(ticket.amount_paid, Decimal('100.00'))
        self.assertTrue(ticket.is_paid)


class ChecklistItemModelTest(TestCase, TestDataMixin):
    """Test the ChecklistItem model."""

    def test_create_checklist_item_for_ticket(self):
        """Test creating a checklist item for a ticket."""
        item = self.create_test_checklist_item(text='Check this')
        self.assertEqual(item.text, 'Check this')
        self.assertFalse(item.is_checked)
        self.assertIsNotNone(item.ticket)

    def test_checklist_item_string_representation(self):
        """Test checklist item __str__ method."""
        ticket = self.create_test_ticket(title='Test')
        item = self.create_test_checklist_item(text='Item 1', ticket=ticket)
        self.assertIn('Item 1', str(item))
        self.assertIn('☐', str(item))

        item.is_checked = True
        item.save()
        self.assertIn('✓', str(item))

    def test_checklist_item_position_auto_increment(self):
        """Test that checklist positions auto-increment."""
        ticket = self.create_test_ticket()
        item1 = self.create_test_checklist_item(ticket=ticket)
        item2 = self.create_test_checklist_item(ticket=ticket)

        # item2 should have position greater than item1
        self.assertGreater(item2.position, item1.position)


class TicketCommentModelTest(TestCase, TestDataMixin):
    """Test the TicketComment model."""

    def test_create_comment(self):
        """Test creating a comment."""
        comment = self.create_test_comment(comment='Great work!')
        self.assertEqual(comment.comment, 'Great work!')
        self.assertIsNotNone(comment.ticket)
        self.assertIsNotNone(comment.user)

    def test_comment_string_representation(self):
        """Test comment __str__ method."""
        ticket = self.create_test_ticket(title='Bug Fix')
        user = self.create_test_user(email='commenter@example.com')
        comment = self.create_test_comment(
            comment='Test comment',
            ticket=ticket,
            user=user
        )
        self.assertIn('Bug Fix', str(comment))
        self.assertIn('commenter@example.com', str(comment))


class TicketTimeLogModelTest(TestCase, TestDataMixin):
    """Test the TicketTimeLog model."""

    def test_create_time_log(self):
        """Test creating a time log."""
        time_log = self.create_test_time_log()
        self.assertIsNotNone(time_log.ticket)
        self.assertIsNotNone(time_log.column)
        self.assertIsNotNone(time_log.entered_at)
        self.assertIsNone(time_log.exited_at)

    def test_time_log_duration_calculation(self):
        """Test duration calculation."""
        time_log = self.create_test_time_log()
        time_log.entered_at = timezone.now() - timedelta(hours=2, minutes=30)
        time_log.exited_at = timezone.now()
        time_log.calculate_duration()

        # Duration should be approximately 9000 seconds (2.5 hours)
        self.assertGreaterEqual(time_log.duration_seconds, 9000)
        self.assertLess(time_log.duration_seconds, 9100)

    def test_time_log_duration_display(self):
        """Test duration display format."""
        time_log = self.create_test_time_log()
        time_log.duration_seconds = 3665  # 1 hour, 1 minute, 5 seconds

        duration = time_log.duration_display
        self.assertIn('1h', duration)


class TicketPaymentModelTest(TestCase, TestDataMixin):
    """Test the TicketPayment model."""

    def test_create_payment(self):
        """Test creating a payment."""
        payment = self.create_test_payment(amount=50.00)
        self.assertEqual(payment.amount, Decimal('50.00'))
        self.assertEqual(payment.currency, 'USD')
        self.assertEqual(payment.payment_method, 'manual')

    def test_payment_string_representation(self):
        """Test payment __str__ method."""
        ticket = self.create_test_ticket(title='Service')
        payment = self.create_test_payment(
            ticket=ticket,
            amount=100.00,
            currency='GEL'
        )
        self.assertIn('100', str(payment))
        self.assertIn('GEL', str(payment))
        self.assertIn('Service', str(payment))

    def test_payment_updates_ticket_amount(self):
        """Test that creating payment updates ticket amount_paid."""
        ticket = self.create_test_ticket(
            price=Decimal('200.00'),
            amount_paid=Decimal('0.00')
        )

        # Use the ticket's add_payment method
        ticket.add_payment(Decimal('50.00'))

        self.assertEqual(ticket.amount_paid, Decimal('50.00'))

        # Verify payment was created
        payments = TicketPayment.objects.filter(ticket=ticket)
        self.assertEqual(payments.count(), 1)
        self.assertEqual(payments.first().amount, Decimal('50.00'))
