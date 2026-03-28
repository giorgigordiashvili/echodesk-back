"""Tests for TicketTimeLogViewSet."""
from django.utils import timezone
from datetime import timedelta
from tickets.tests.conftest import TicketTestCase


class TestTimeLogRead(TicketTestCase):

    def test_list_time_logs(self):
        admin = self.create_admin()
        board, col1, col2, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        self.create_time_log(ticket, col1, admin)
        resp = self.api_get('/api/time-logs/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(self.get_results(resp)), 1)

    def test_filter_by_ticket(self):
        admin = self.create_admin()
        board, col1, col2, _ = self.setup_board_with_columns(admin=admin)
        t1 = self.create_ticket(title='T1', column=col1, created_by=admin)
        t2 = self.create_ticket(title='T2', column=col1, created_by=admin)
        self.create_time_log(t1, col1, admin)
        self.create_time_log(t2, col1, admin)
        resp = self.api_get(f'/api/time-logs/?ticket={t1.id}', user=admin)
        self.assertEqual(len(self.get_results(resp)), 1)

    def test_filter_by_user(self):
        admin = self.create_admin()
        user = self.create_user(email='tlu@test.com')
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        self.create_time_log(ticket, col1, admin)
        self.create_time_log(ticket, col1, user)
        resp = self.api_get(f'/api/time-logs/?user={user.id}', user=admin)
        self.assertEqual(len(self.get_results(resp)), 1)


class TestTimeLogPermissions(TicketTestCase):

    def test_staff_sees_all_time_logs(self):
        admin = self.create_admin()
        user = self.create_user(email='tlu2@test.com')
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=user)
        self.create_time_log(ticket, col1, user)
        resp = self.api_get('/api/time-logs/', user=admin)
        self.assertGreaterEqual(len(self.get_results(resp)), 1)

    def test_non_staff_sees_own_ticket_logs(self):
        admin = self.create_admin()
        user = self.create_user(email='tlu3@test.com')
        other = self.create_user(email='tlu4@test.com')
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        t_own = self.create_ticket(title='Own', column=col1, created_by=user)
        t_other = self.create_ticket(title='Other', column=col1, created_by=other)
        self.create_time_log(t_own, col1, user)
        self.create_time_log(t_other, col1, other)
        resp = self.api_get('/api/time-logs/', user=user)
        ticket_titles = [log['ticket'] for log in self.get_results(resp)]
        self.assertTrue(any('Own' in t for t in ticket_titles))

    def test_read_only(self):
        admin = self.create_admin()
        resp = self.api_post('/api/time-logs/', {'ticket': 1}, user=admin)
        self.assertEqual(resp.status_code, 405)


class TestMyTimeSummary(TicketTestCase):

    def test_my_time_summary(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        now = timezone.now()
        self.create_time_log(
            ticket, col1, admin,
            exited_at=now, duration_seconds=3600
        )
        resp = self.api_get('/api/time-logs/my_time_summary/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('total_time_seconds', resp.data)

    def test_my_time_summary_invalid_days(self):
        """Validates Bug 4 fix: ?days=abc returns 400."""
        admin = self.create_admin()
        resp = self.api_get('/api/time-logs/my_time_summary/?days=abc', user=admin)
        self.assertEqual(resp.status_code, 400)
