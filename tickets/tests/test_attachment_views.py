"""Tests for TicketAttachmentViewSet."""
from tickets.tests.conftest import TicketTestCase


class TestAttachmentCRUD(TicketTestCase):

    def test_list_attachments(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        self.create_attachment(ticket, uploaded_by=admin)
        resp = self.api_get('/api/attachments/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(self.get_results(resp)), 1)

    def test_filter_by_ticket(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        t1 = self.create_ticket(title='T1', column=col1, created_by=admin)
        t2 = self.create_ticket(title='T2', column=col1, created_by=admin)
        self.create_attachment(t1, uploaded_by=admin)
        self.create_attachment(t2, uploaded_by=admin)
        resp = self.api_get(f'/api/attachments/?ticket={t1.id}', user=admin)
        self.assertEqual(len(self.get_results(resp)), 1)

    def test_delete_attachment(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        att = self.create_attachment(ticket, uploaded_by=admin)
        resp = self.api_delete(f'/api/attachments/{att.id}/', user=admin)
        self.assertEqual(resp.status_code, 204)


class TestAttachmentPermissions(TicketTestCase):

    def test_staff_sees_all_attachments(self):
        admin = self.create_admin()
        user = self.create_user(email='attu@test.com')
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=user)
        self.create_attachment(ticket, uploaded_by=user)
        resp = self.api_get('/api/attachments/', user=admin)
        self.assertGreaterEqual(len(self.get_results(resp)), 1)

    def test_non_staff_sees_accessible_ticket_attachments(self):
        admin = self.create_admin()
        user = self.create_user(email='attacc@test.com')
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=user)
        self.create_attachment(ticket, uploaded_by=user)
        resp = self.api_get('/api/attachments/', user=user)
        self.assertGreaterEqual(len(self.get_results(resp)), 1)

    def test_non_staff_cannot_see_inaccessible_attachments(self):
        admin = self.create_admin()
        user1 = self.create_user(email='att1@test.com')
        user2 = self.create_user(email='att2@test.com')
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        # Restrict board
        board.board_users.add(user1)
        ticket = self.create_ticket(title='Secret', column=col1, created_by=user1)
        self.create_attachment(ticket, uploaded_by=user1)
        resp = self.api_get('/api/attachments/', user=user2)
        self.assertEqual(len(self.get_results(resp)), 0)
