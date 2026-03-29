"""Tests for BoardViewSet."""
from django.db.models import Count
from tickets.models import Board
from tickets.tests.conftest import TicketTestCase


class TestBoardCRUD(TicketTestCase):

    def test_admin_can_create_board(self):
        admin = self.create_admin()
        resp = self.api_post('/api/boards/', {'name': 'New Board'}, user=admin)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['name'], 'New Board')

    def test_admin_can_update_board(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        resp = self.api_patch(f'/api/boards/{board.id}/', {'name': 'Updated'}, user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['name'], 'Updated')

    def test_admin_can_delete_board(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        resp = self.api_delete(f'/api/boards/{board.id}/', user=admin)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Board.objects.filter(id=board.id).exists())

    def test_list_boards(self):
        admin = self.create_admin()
        self.create_board(name='Board A', created_by=admin)
        self.create_board(name='Board B', created_by=admin)
        resp = self.api_get('/api/boards/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.get_results(resp)), 2)


class TestBoardPermissions(TicketTestCase):

    def test_staff_can_access_all_boards(self):
        admin = self.create_admin()
        self.create_board(name='Board 1', created_by=admin)
        self.create_board(name='Board 2', created_by=admin)
        resp = self.api_get('/api/boards/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.get_results(resp)), 2)

    def test_unauthenticated_denied(self):
        resp = self.api_get('/api/boards/')
        self.assertIn(resp.status_code, [401, 403])

    def test_user_with_view_boards_permission(self):
        user = self.create_user(email='viewer@test.com', can_view_boards=True)
        admin = self.create_admin()
        self.create_board(name='B1', created_by=admin)
        resp = self.api_get('/api/boards/', user=user)
        self.assertEqual(resp.status_code, 200)

    def test_user_with_access_orders_permission(self):
        user = self.create_user(email='order@test.com', can_access_orders=True)
        admin = self.create_admin()
        self.create_board(name='B1', created_by=admin)
        resp = self.api_get('/api/boards/', user=user)
        self.assertEqual(resp.status_code, 200)

    def test_user_in_board_group_can_access(self):
        user = self.create_user(email='groupuser@test.com')
        group = self.create_tenant_group(name='Sales')
        user.tenant_groups.add(group)
        admin = self.create_admin()
        board = self.create_board(name='Restricted Board', created_by=admin)
        board.board_groups.add(group)
        resp = self.api_get('/api/boards/', user=user)
        self.assertEqual(resp.status_code, 200)
        board_ids = [b['id'] for b in self.get_results(resp)]
        self.assertIn(board.id, board_ids)

    def test_user_directly_attached_can_access(self):
        user = self.create_user(email='directuser@test.com')
        admin = self.create_admin()
        board = self.create_board(name='Direct Board', created_by=admin)
        board.board_users.add(user)
        resp = self.api_get('/api/boards/', user=user)
        self.assertEqual(resp.status_code, 200)
        board_ids = [b['id'] for b in self.get_results(resp)]
        self.assertIn(board.id, board_ids)

    def test_user_without_access_cannot_see_restricted_board(self):
        # User has view_boards to pass permission check, but can't see restricted boards
        user = self.create_user(email='noaccuser@test.com', can_view_boards=True)
        admin = self.create_admin()
        board = self.create_board(name='Restricted', created_by=admin)
        # Add a restriction (some user, not our test user)
        other_user = self.create_user(email='other@test.com')
        board.board_users.add(other_user)
        resp = self.api_get('/api/boards/', user=user)
        self.assertEqual(resp.status_code, 200)
        board_ids = [b['id'] for b in self.get_results(resp)]
        self.assertNotIn(board.id, board_ids)

    def test_unrestricted_board_visible_to_all(self):
        # User with view_boards perm can see unrestricted boards
        user = self.create_user(email='anyuser@test.com', can_view_boards=True)
        admin = self.create_admin()
        board = self.create_board(name='Open Board', created_by=admin)
        # No board_users or board_groups — unrestricted
        resp = self.api_get('/api/boards/', user=user)
        self.assertEqual(resp.status_code, 200)
        board_ids = [b['id'] for b in self.get_results(resp)]
        self.assertIn(board.id, board_ids)


class TestBoardActions(TicketTestCase):

    def test_set_default(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        resp = self.api_post(f'/api/boards/{board.id}/set_default/', user=admin)
        self.assertEqual(resp.status_code, 200)
        board.refresh_from_db()
        self.assertTrue(board.is_default)

    def test_non_staff_cannot_set_default(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin)
        user = self.create_user(email='viewer@test.com', can_view_boards=True)
        resp = self.api_post(f'/api/boards/{board.id}/set_default/', user=user)
        self.assertEqual(resp.status_code, 403)

    def test_get_default_board(self):
        admin = self.create_admin()
        board = self.create_board(created_by=admin, is_default=True)
        resp = self.api_get('/api/boards/default/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['id'], board.id)

    def test_get_default_returns_404_when_none(self):
        admin = self.create_admin()
        # No boards exist
        resp = self.api_get('/api/boards/default/', user=admin)
        self.assertEqual(resp.status_code, 404)

    def test_kanban_board_action(self):
        admin = self.create_admin()
        board, col1, col2, col3 = self.setup_board_with_columns(admin=admin)
        self.create_ticket(title='T1', column=col1, created_by=admin)
        resp = self.api_get(f'/api/boards/{board.id}/kanban_board/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('columns', resp.data)
        self.assertIn('tickets_by_column', resp.data)


class TestBoardQueryset(TicketTestCase):

    def test_staff_sees_all_boards(self):
        admin = self.create_admin()
        self.create_board(name='B1', created_by=admin)
        self.create_board(name='B2', created_by=admin)
        resp = self.api_get('/api/boards/', user=admin)
        self.assertEqual(len(self.get_results(resp)), 2)

    def test_regular_user_sees_accessible_boards_only(self):
        admin = self.create_admin()
        user = self.create_user(email='reguser@test.com', can_view_boards=True)
        open_board = self.create_board(name='Open', created_by=admin)
        restricted = self.create_board(name='Restricted', created_by=admin)
        other = self.create_user(email='other2@test.com')
        restricted.board_users.add(other)
        resp = self.api_get('/api/boards/', user=user)
        board_ids = [b['id'] for b in self.get_results(resp)]
        self.assertIn(open_board.id, board_ids)
        self.assertNotIn(restricted.id, board_ids)
