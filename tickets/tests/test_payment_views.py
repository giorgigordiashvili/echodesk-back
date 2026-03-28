"""Tests for TicketPaymentViewSet."""
from decimal import Decimal
from tickets.models import Ticket
from tickets.tests.conftest import TicketTestCase


class TestPaymentCRUD(TicketTestCase):

    def test_list_payments(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin, price=Decimal('100.00'))
        self.create_payment(ticket, amount=Decimal('50.00'), processed_by=admin)
        resp = self.api_get('/api/payments/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(self.get_results(resp)), 1)

    def test_filter_payments_by_ticket(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        t1 = self.create_ticket(title='T1', column=col1, created_by=admin, price=Decimal('100'))
        t2 = self.create_ticket(title='T2', column=col1, created_by=admin, price=Decimal('100'))
        self.create_payment(t1, amount=Decimal('10'), processed_by=admin)
        self.create_payment(t2, amount=Decimal('20'), processed_by=admin)
        resp = self.api_get(f'/api/payments/?ticket={t1.id}', user=admin)
        self.assertEqual(len(self.get_results(resp)), 1)


class TestPaymentPermissions(TicketTestCase):

    def test_superuser_sees_all_payments(self):
        admin = self.create_admin()
        admin.is_superuser = True
        admin.save()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        user = self.create_user(email='payuser@test.com')
        ticket = self.create_ticket(title='T', column=col1, created_by=user, price=Decimal('100'))
        self.create_payment(ticket, amount=Decimal('10'), processed_by=user)
        resp = self.api_get('/api/payments/', user=admin)
        self.assertGreaterEqual(len(self.get_results(resp)), 1)

    def test_regular_user_sees_own_ticket_payments(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        user = self.create_user(email='payusr@test.com')
        other = self.create_user(email='payoth@test.com')
        t_own = self.create_ticket(title='Own', column=col1, created_by=user, price=Decimal('50'))
        t_other = self.create_ticket(title='Other', column=col1, created_by=other, price=Decimal('50'))
        self.create_payment(t_own, amount=Decimal('10'), processed_by=user)
        self.create_payment(t_other, amount=Decimal('10'), processed_by=other)
        resp = self.api_get('/api/payments/', user=user)
        ticket_ids = [p['ticket'] for p in self.get_results(resp)]
        self.assertIn(t_own.id, ticket_ids)


class TestProcessPayment(TicketTestCase):

    def test_process_payment_success(self):
        admin = self.create_admin()
        admin.is_superuser = True
        admin.save()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin, price=Decimal('100'))
        resp = self.api_post('/api/payments/process_payment/', {
            'ticket_id': ticket.id, 'amount': '50.00'
        }, user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('remaining_balance', resp.data)

    def test_process_payment_missing_fields(self):
        admin = self.create_admin()
        resp = self.api_post('/api/payments/process_payment/', {}, user=admin)
        self.assertEqual(resp.status_code, 400)

    def test_process_payment_invalid_ticket(self):
        admin = self.create_admin()
        resp = self.api_post('/api/payments/process_payment/', {
            'ticket_id': 99999, 'amount': '10.00'
        }, user=admin)
        self.assertEqual(resp.status_code, 400)

    def test_process_payment_permission_denied(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin, price=Decimal('100'))
        stranger = self.create_user(email='paystranger@test.com')
        resp = self.api_post('/api/payments/process_payment/', {
            'ticket_id': ticket.id, 'amount': '10.00'
        }, user=stranger)
        self.assertEqual(resp.status_code, 403)

    def test_process_payment_auto_marks_paid(self):
        admin = self.create_admin()
        admin.is_superuser = True
        admin.save()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin, price=Decimal('100'))
        self.api_post('/api/payments/process_payment/', {
            'ticket_id': ticket.id, 'amount': '100.00'
        }, user=admin)
        ticket.refresh_from_db()
        self.assertTrue(ticket.is_paid)

    def test_process_payment_decimal_precision(self):
        """Validates Bug 3 fix: Decimal amounts handled correctly."""
        admin = self.create_admin()
        admin.is_superuser = True
        admin.save()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin, price=Decimal('0.30'))
        # With float, 0.1 + 0.2 != 0.3; with Decimal it works correctly
        self.api_post('/api/payments/process_payment/', {
            'ticket_id': ticket.id, 'amount': '0.10'
        }, user=admin)
        self.api_post('/api/payments/process_payment/', {
            'ticket_id': ticket.id, 'amount': '0.20'
        }, user=admin)
        ticket.refresh_from_db()
        self.assertEqual(ticket.amount_paid, Decimal('0.30'))
        self.assertTrue(ticket.is_paid)


class TestPaymentSummary(TicketTestCase):

    def test_payment_summary(self):
        admin = self.create_admin()
        admin.is_superuser = True
        admin.save()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        self.create_ticket(title='T', column=col1, created_by=admin, price=Decimal('100'))
        resp = self.api_get('/api/payments/payment_summary/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('total_tickets', resp.data)

    def test_payment_summary_filter_by_board(self):
        admin = self.create_admin()
        admin.is_superuser = True
        admin.save()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        self.create_ticket(title='T', column=col1, created_by=admin, price=Decimal('100'))
        resp = self.api_get(f'/api/payments/payment_summary/?board_id={board.id}', user=admin)
        self.assertEqual(resp.status_code, 200)
