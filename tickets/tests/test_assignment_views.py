"""Tests for TicketAssignmentViewSet."""
from tickets.models import TicketAssignment
from tickets.tests.conftest import TicketTestCase


class TestAssignmentCRUD(TicketTestCase):

    def test_create_assignment_via_bulk(self):
        """Single assignment creation uses bulk_assign since serializer has user read_only."""
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        user = self.create_user(email='assign_target@test.com')
        resp = self.api_post(
            f'/api/tickets/{ticket.id}/assignments/bulk_assign/',
            {'user_ids': [user.id], 'roles': {str(user.id): 'collaborator'}},
            user=admin
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(self.get_results(resp)), 1)

    def test_list_assignments(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        user = self.create_user(email='asgn@test.com')
        self.create_assignment(ticket, user, assigned_by=admin)
        resp = self.api_get(f'/api/tickets/{ticket.id}/assignments/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.get_results(resp)), 1)

    def test_delete_assignment(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        user = self.create_user(email='asgn2@test.com')
        assignment = self.create_assignment(ticket, user, assigned_by=admin)
        resp = self.api_delete(
            f'/api/tickets/{ticket.id}/assignments/{assignment.id}/', user=admin
        )
        self.assertEqual(resp.status_code, 204)


class TestBulkAssignment(TicketTestCase):

    def test_bulk_assign(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        u1 = self.create_user(email='ba1@test.com')
        u2 = self.create_user(email='ba2@test.com')
        resp = self.api_post(
            f'/api/tickets/{ticket.id}/assignments/bulk_assign/',
            {'user_ids': [u1.id, u2.id]}, user=admin
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(len(self.get_results(resp)), 2)

    def test_bulk_assign_with_roles(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        u1 = self.create_user(email='br1@test.com')
        resp = self.api_post(
            f'/api/tickets/{ticket.id}/assignments/bulk_assign/',
            {'user_ids': [u1.id], 'roles': {str(u1.id): 'primary'}}, user=admin
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(self.get_results(resp)[0]['role'], 'primary')

    def test_bulk_assign_replace(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        u1 = self.create_user(email='rep1@test.com')
        u2 = self.create_user(email='rep2@test.com')
        self.create_assignment(ticket, u1, assigned_by=admin)
        resp = self.api_post(
            f'/api/tickets/{ticket.id}/assignments/bulk_assign/',
            {'user_ids': [u2.id], 'replace': True}, user=admin
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(TicketAssignment.objects.filter(ticket=ticket).count(), 1)
        self.assertEqual(TicketAssignment.objects.filter(ticket=ticket).first().user_id, u2.id)

    def test_bulk_unassign(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        u1 = self.create_user(email='un1@test.com')
        self.create_assignment(ticket, u1, assigned_by=admin)
        client = self.authenticated_client(admin)
        resp = client.delete(
            f'/api/tickets/{ticket.id}/assignments/bulk_unassign/',
            data={'user_ids': [u1.id]}, format='json',
            HTTP_HOST='tenant.test.com'
        )
        self.assertIn(resp.status_code, [200, 204])

    def test_unique_constraint(self):
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        u1 = self.create_user(email='dup1@test.com')
        self.create_assignment(ticket, u1, assigned_by=admin)
        # Bulk assign same user again — uses get_or_create
        resp = self.api_post(
            f'/api/tickets/{ticket.id}/assignments/bulk_assign/',
            {'user_ids': [u1.id]}, user=admin
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(TicketAssignment.objects.filter(ticket=ticket, user=u1).count(), 1)

    def test_create_assignment_nonexistent_ticket(self):
        """POST to create assignment on nonexistent ticket returns 404."""
        admin = self.create_admin()
        target = self.create_user(email='target_ne@test.com')
        resp = self.api_post(
            '/api/tickets/99999/assignments/',
            {'user': target.id, 'role': 'collaborator'}, user=admin
        )
        self.assertEqual(resp.status_code, 404)

    def test_bulk_assign_nonexistent_ticket(self):
        """POST to nonexistent ticket returns 404."""
        admin = self.create_admin()
        resp = self.api_post(
            '/api/tickets/99999/assignments/bulk_assign/',
            {'user_ids': [admin.id]}, user=admin
        )
        self.assertEqual(resp.status_code, 404)

    def test_bulk_unassign_nonexistent_ticket(self):
        """DELETE to nonexistent ticket returns 404."""
        admin = self.create_admin()
        client = self.authenticated_client(admin)
        resp = client.delete(
            '/api/tickets/99999/assignments/bulk_unassign/',
            data={'user_ids': [admin.id]}, format='json',
            HTTP_HOST='tenant.test.com'
        )
        self.assertEqual(resp.status_code, 404)

    def test_bulk_assign_permission_check(self):
        """Validates Bug 2 fix: non-staff/non-owner cannot bulk assign."""
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        stranger = self.create_user(email='stranger@test.com')
        u1 = self.create_user(email='target3@test.com')
        resp = self.api_post(
            f'/api/tickets/{ticket.id}/assignments/bulk_assign/',
            {'user_ids': [u1.id]}, user=stranger
        )
        self.assertEqual(resp.status_code, 403)

    def test_bulk_unassign_permission_check(self):
        """Validates Bug 2 fix: non-staff/non-owner cannot bulk unassign."""
        admin = self.create_admin()
        board, col1, _, _ = self.setup_board_with_columns(admin=admin)
        ticket = self.create_ticket(title='T', column=col1, created_by=admin)
        u1 = self.create_user(email='ua1@test.com')
        self.create_assignment(ticket, u1, assigned_by=admin)
        stranger = self.create_user(email='stranger2@test.com')
        client = self.authenticated_client(stranger)
        resp = client.delete(
            f'/api/tickets/{ticket.id}/assignments/bulk_unassign/',
            data={'user_ids': [u1.id]}, format='json',
            HTTP_HOST='tenant.test.com'
        )
        self.assertEqual(resp.status_code, 403)
