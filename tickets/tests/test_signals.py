"""
Tests for tickets/signals.py — record_ticket_history pre_save signal.

Verifies that TicketHistory entries are created when tracked fields change,
and that new ticket creation does NOT produce history records.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model

from tickets.tests.conftest import TicketTestCase
from tickets.models import TicketHistory

User = get_user_model()

# Suppress WebSocket/push side effects from post_save signals.
# async_to_sync is imported at module level in tickets/signals.py
_ws_patch = patch('tickets.signals.async_to_sync', return_value=lambda **kw: None)
# In notification_utils, async_to_sync is imported inside the function body,
# so we patch it at the source module.
_notif_patch = patch(
    'asgiref.sync.async_to_sync',
    return_value=lambda f: (lambda **kw: None),
)
_incr_patch = patch('users.notification_utils.increment_unread')


class TestRecordTicketHistory(TicketTestCase):

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin(email='hist-admin@test.com')
        self.board, self.col_todo, self.col_progress, self.col_done = (
            self.setup_board_with_columns(admin=self.admin)
        )
        self.other_user = self.create_user(email='hist-other@test.com')

    # ── Helpers ──
    def _clear_history(self, ticket):
        TicketHistory.objects.filter(ticket=ticket).delete()

    # ── Tests ──
    @_ws_patch
    @_notif_patch
    @_incr_patch
    def test_new_ticket_does_not_create_history(self, *mocks):
        ticket = self.create_ticket(
            title='Brand New',
            column=self.col_todo,
            created_by=self.admin,
        )
        histories = TicketHistory.objects.filter(ticket=ticket)
        self.assertEqual(histories.count(), 0)

    @_ws_patch
    @_notif_patch
    @_incr_patch
    def test_title_change_creates_history(self, *mocks):
        ticket = self.create_ticket(
            title='Original Title',
            column=self.col_todo,
            created_by=self.admin,
        )
        self._clear_history(ticket)

        ticket.title = 'Updated Title'
        ticket.save()

        h = TicketHistory.objects.filter(ticket=ticket, field_name='title')
        self.assertEqual(h.count(), 1)
        entry = h.first()
        self.assertEqual(entry.action, 'updated')
        self.assertEqual(entry.old_value, 'Original Title')
        self.assertEqual(entry.new_value, 'Updated Title')

    @_ws_patch
    @_notif_patch
    @_incr_patch
    def test_priority_change_creates_history(self, *mocks):
        ticket = self.create_ticket(
            title='Priority Test',
            column=self.col_todo,
            created_by=self.admin,
            priority='low',
        )
        self._clear_history(ticket)

        ticket.priority = 'critical'
        ticket.save()

        h = TicketHistory.objects.filter(ticket=ticket, field_name='priority')
        self.assertEqual(h.count(), 1)
        entry = h.first()
        self.assertEqual(entry.action, 'priority_changed')
        self.assertEqual(entry.old_value, 'low')
        self.assertEqual(entry.new_value, 'critical')

    @_ws_patch
    @_notif_patch
    @_incr_patch
    def test_column_change_creates_status_changed_history(self, *mocks):
        ticket = self.create_ticket(
            title='Status Test',
            column=self.col_todo,
            created_by=self.admin,
        )
        self._clear_history(ticket)

        ticket.column = self.col_progress
        ticket.save()

        h = TicketHistory.objects.filter(ticket=ticket, field_name='column_id')
        self.assertEqual(h.count(), 1)
        entry = h.first()
        self.assertEqual(entry.action, 'status_changed')
        self.assertEqual(entry.old_value, str(self.col_todo.pk))
        self.assertEqual(entry.new_value, str(self.col_progress.pk))

    @_ws_patch
    @_notif_patch
    @_incr_patch
    def test_assigned_to_change_creates_history(self, *mocks):
        ticket = self.create_ticket(
            title='Assign Test',
            column=self.col_todo,
            created_by=self.admin,
        )
        self._clear_history(ticket)

        ticket.assigned_to = self.other_user
        ticket.save()

        h = TicketHistory.objects.filter(ticket=ticket, field_name='assigned_to_id')
        self.assertEqual(h.count(), 1)
        entry = h.first()
        self.assertEqual(entry.action, 'assigned')
        self.assertEqual(entry.old_value, '')  # was None
        self.assertEqual(entry.new_value, str(self.other_user.pk))

    @_ws_patch
    @_notif_patch
    @_incr_patch
    def test_multiple_field_changes_create_multiple_entries(self, *mocks):
        ticket = self.create_ticket(
            title='Multi Field',
            column=self.col_todo,
            created_by=self.admin,
            priority='low',
        )
        self._clear_history(ticket)

        ticket.title = 'Changed Title'
        ticket.priority = 'high'
        ticket.column = self.col_done
        ticket.save()

        histories = TicketHistory.objects.filter(ticket=ticket)
        changed_fields = set(histories.values_list('field_name', flat=True))
        self.assertIn('title', changed_fields)
        self.assertIn('priority', changed_fields)
        self.assertIn('column_id', changed_fields)
        self.assertEqual(histories.count(), 3)

    @_ws_patch
    @_notif_patch
    @_incr_patch
    def test_description_change_creates_history(self, *mocks):
        ticket = self.create_ticket(
            title='Desc Test',
            column=self.col_todo,
            created_by=self.admin,
            description='Old description',
        )
        self._clear_history(ticket)

        ticket.description = 'New description'
        ticket.save()

        h = TicketHistory.objects.filter(ticket=ticket, field_name='description')
        self.assertEqual(h.count(), 1)
        entry = h.first()
        self.assertEqual(entry.action, 'updated')

    @_ws_patch
    @_notif_patch
    @_incr_patch
    def test_no_change_does_not_create_history(self, *mocks):
        ticket = self.create_ticket(
            title='No Change',
            column=self.col_todo,
            created_by=self.admin,
        )
        self._clear_history(ticket)

        # Save without changes
        ticket.save()

        histories = TicketHistory.objects.filter(ticket=ticket)
        self.assertEqual(histories.count(), 0)
