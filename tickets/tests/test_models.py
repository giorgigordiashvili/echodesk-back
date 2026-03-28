"""Tests for ticket models: properties, save logic, and custom methods."""
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from tickets.models import (
    Ticket, TicketColumn, Board, TicketTimeLog, TicketPayment,
)
from tickets.tests.conftest import TicketTestCase


class TestTicketModel(TicketTestCase):

    def test_status_property(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='In Progress', position=0, created_by=admin)
        ticket = self.create_ticket(title='T', column=col, created_by=admin)
        self.assertEqual(ticket.status, 'in_progress')

    def test_status_property_no_column(self):
        admin = self.create_admin()
        ticket = Ticket(title='T', created_by=admin)
        ticket.column = None
        self.assertEqual(ticket.status, 'unassigned')

    def test_is_closed_property(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='Done', position=0, is_closed_status=True, created_by=admin)
        ticket = self.create_ticket(title='T', column=col, created_by=admin)
        self.assertTrue(ticket.is_closed)

    def test_is_closed_false(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='Open', position=0, is_closed_status=False, created_by=admin)
        ticket = self.create_ticket(title='T', column=col, created_by=admin)
        self.assertFalse(ticket.is_closed)

    def test_remaining_balance(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='C', position=0, created_by=admin)
        ticket = self.create_ticket(
            title='T', column=col, created_by=admin,
            price=Decimal('100.00'), amount_paid=Decimal('30.00')
        )
        self.assertEqual(ticket.remaining_balance, Decimal('70.00'))

    def test_remaining_balance_no_price(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='C', position=0, created_by=admin)
        ticket = self.create_ticket(title='T', column=col, created_by=admin)
        self.assertIsNone(ticket.remaining_balance)

    def test_payment_status_property(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='C', position=0, created_by=admin)

        # no_payment_required
        t1 = self.create_ticket(title='NoPay', column=col, created_by=admin)
        self.assertEqual(t1.payment_status, 'no_payment_required')

        # unpaid
        t2 = self.create_ticket(title='Unpaid', column=col, created_by=admin, price=Decimal('100'))
        self.assertEqual(t2.payment_status, 'unpaid')

        # partially_paid
        t3 = self.create_ticket(
            title='Partial', column=col, created_by=admin,
            price=Decimal('100'), amount_paid=Decimal('50')
        )
        self.assertEqual(t3.payment_status, 'partially_paid')

        # paid
        t4 = self.create_ticket(
            title='Paid', column=col, created_by=admin,
            price=Decimal('100'), amount_paid=Decimal('100'), is_paid=True
        )
        self.assertEqual(t4.payment_status, 'paid')

        # overpaid — model save() auto-sets is_paid=True when amount_paid >= price,
        # so payment_status returns 'paid' (is_paid check comes first in the property)
        t5 = self.create_ticket(
            title='Over', column=col, created_by=admin,
            price=Decimal('100'), amount_paid=Decimal('150')
        )
        self.assertEqual(t5.payment_status, 'paid')

    def test_is_overdue(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='C', position=0, created_by=admin)
        past = timezone.now().date() - timedelta(days=10)
        ticket = self.create_ticket(
            title='Overdue', column=col, created_by=admin,
            price=Decimal('100'), payment_due_date=past
        )
        self.assertTrue(ticket.is_overdue)

    def test_is_not_overdue_when_paid(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='C', position=0, created_by=admin)
        past = timezone.now().date() - timedelta(days=10)
        ticket = self.create_ticket(
            title='Paid', column=col, created_by=admin,
            price=Decimal('100'), amount_paid=Decimal('100'),
            is_paid=True, payment_due_date=past
        )
        self.assertFalse(ticket.is_overdue)

    def test_add_payment(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='C', position=0, created_by=admin)
        ticket = self.create_ticket(
            title='Pay', column=col, created_by=admin, price=Decimal('100')
        )
        remaining = ticket.add_payment(Decimal('40'), admin)
        self.assertEqual(remaining, Decimal('60'))
        self.assertEqual(ticket.amount_paid, Decimal('40'))
        self.assertTrue(TicketPayment.objects.filter(ticket=ticket, amount=Decimal('40')).exists())

    def test_add_payment_auto_marks_paid(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='C', position=0, created_by=admin)
        ticket = self.create_ticket(
            title='FullPay', column=col, created_by=admin, price=Decimal('50')
        )
        ticket.add_payment(Decimal('50'), admin)
        self.assertTrue(ticket.is_paid)

    def test_add_payment_negative_raises(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='C', position=0, created_by=admin)
        ticket = self.create_ticket(
            title='Neg', column=col, created_by=admin, price=Decimal('100')
        )
        with self.assertRaises(ValueError):
            ticket.add_payment(Decimal('-10'), admin)

    def test_auto_default_column_on_save(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='Default', position=0, is_default=True, created_by=admin)
        ticket = Ticket.objects.create(title='Auto', created_by=admin)
        self.assertEqual(ticket.column_id, col.id)

    def test_auto_position_on_save(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='C', position=0, created_by=admin)
        t1 = self.create_ticket(title='T1', column=col, created_by=admin)
        t2 = self.create_ticket(title='T2', column=col, created_by=admin)
        self.assertGreater(t2.position_in_column, t1.position_in_column)


class TestColumnModel(TicketTestCase):

    def test_unique_default_per_board(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col1 = self.create_column(board, name='C1', position=0, is_default=True, created_by=admin)
        col2 = self.create_column(board, name='C2', position=1, is_default=True, created_by=admin)
        col1.refresh_from_db()
        self.assertFalse(col1.is_default)
        self.assertTrue(col2.is_default)

    def test_unique_name_per_board(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        self.create_column(board, name='Same', position=0, created_by=admin)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            self.create_column(board, name='Same', position=1, created_by=admin)


class TestBoardModel(TicketTestCase):

    def test_set_default_unsets_others(self):
        admin = self.create_admin()
        b1 = self.create_board(name='B1', created_by=admin, is_default=True)
        b2 = self.create_board(name='B2', created_by=admin, is_default=True)
        b1.refresh_from_db()
        self.assertFalse(b1.is_default)
        self.assertTrue(b2.is_default)

    def test_get_payment_summary(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='C', position=0, created_by=admin)
        self.create_ticket(
            title='T1', column=col, created_by=admin,
            price=Decimal('100'), amount_paid=Decimal('50')
        )
        self.create_ticket(
            title='T2', column=col, created_by=admin,
            price=Decimal('200'), is_paid=True, amount_paid=Decimal('200')
        )
        summary = board.get_payment_summary()
        self.assertEqual(summary['total_tickets'], 2)
        self.assertEqual(summary['total_price'], Decimal('300'))
        self.assertEqual(summary['total_paid'], Decimal('250'))
        self.assertEqual(summary['remaining_balance'], Decimal('50'))


class TestTimeLogModel(TicketTestCase):

    def test_duration_display_active(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='C', position=0, created_by=admin)
        ticket = self.create_ticket(title='T', column=col, created_by=admin)
        log = self.create_time_log(ticket, col, admin)
        display = log.duration_display
        self.assertIn('active', display.lower())

    def test_calculate_duration(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        col = self.create_column(board, name='C', position=0, created_by=admin)
        ticket = self.create_ticket(title='T', column=col, created_by=admin)
        now = timezone.now()
        log = self.create_time_log(ticket, col, admin)
        log.exited_at = now + timedelta(hours=1)
        log.save()
        log.calculate_duration()
        self.assertIsNotNone(log.duration_seconds)
        self.assertAlmostEqual(log.duration_seconds, 3600, delta=5)
