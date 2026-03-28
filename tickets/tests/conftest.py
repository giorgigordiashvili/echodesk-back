"""
Shared test infrastructure for tickets app tests.
Extends EchoDeskTenantTestCase with ticket-specific helpers.
"""
from decimal import Decimal
from django.utils import timezone
from users.tests.conftest import EchoDeskTenantTestCase
from tickets.models import (
    Board, TicketColumn, Ticket, Tag, ChecklistItem, TicketComment,
    TicketAssignment, TicketTimeLog, TicketPayment,
    ItemList, ListItem, TicketForm, TicketFormSubmission, TicketAttachment,
)


class TicketTestCase(EchoDeskTenantTestCase):
    """
    Ticket-specific test case with factory helpers for all ticket models.
    """

    @staticmethod
    def get_results(resp):
        """Extract results from a paginated or non-paginated response."""
        if isinstance(resp.data, dict) and 'results' in resp.data:
            return resp.data['results']
        return resp.data

    def create_board(self, name='Test Board', created_by=None, **kwargs):
        if created_by is None:
            created_by = self.create_admin(email=f'board-admin-{Board.objects.count()}@test.com')
        return Board.objects.create(name=name, created_by=created_by, **kwargs)

    def create_column(self, board, name='To Do', position=0, created_by=None, **kwargs):
        if created_by is None:
            created_by = board.created_by
        return TicketColumn.objects.create(
            board=board, name=name, position=position, created_by=created_by, **kwargs
        )

    def create_ticket(self, title='Test Ticket', column=None, created_by=None, **kwargs):
        if created_by is None:
            created_by = self.create_user(email=f'ticket-user-{Ticket.objects.count()}@test.com')
        return Ticket.objects.create(title=title, column=column, created_by=created_by, **kwargs)

    def create_tag(self, name='Bug', **kwargs):
        return Tag.objects.create(name=name, **kwargs)

    def create_checklist_item(self, ticket, text='Item 1', created_by=None, **kwargs):
        if created_by is None:
            created_by = ticket.created_by
        return ChecklistItem.objects.create(ticket=ticket, text=text, created_by=created_by, **kwargs)

    def create_comment(self, ticket, user, comment='Test comment'):
        return TicketComment.objects.create(ticket=ticket, user=user, comment=comment)

    def create_assignment(self, ticket, user, role='collaborator', assigned_by=None):
        return TicketAssignment.objects.create(
            ticket=ticket, user=user, role=role, assigned_by=assigned_by
        )

    def create_time_log(self, ticket, column, user, **kwargs):
        return TicketTimeLog.objects.create(ticket=ticket, column=column, user=user, **kwargs)

    def create_payment(self, ticket, amount=Decimal('10.00'), **kwargs):
        return TicketPayment.objects.create(
            ticket=ticket, amount=amount, currency=ticket.currency,
            payment_method='manual', **kwargs
        )

    def create_item_list(self, title='Test List', created_by=None, **kwargs):
        if created_by is None:
            created_by = self.create_admin(email=f'list-admin-{ItemList.objects.count()}@test.com')
        return ItemList.objects.create(title=title, created_by=created_by, **kwargs)

    def create_list_item(self, item_list, label='Item 1', created_by=None, **kwargs):
        if created_by is None:
            created_by = item_list.created_by
        return ListItem.objects.create(item_list=item_list, label=label, created_by=created_by, **kwargs)

    def create_ticket_form(self, title='Test Form', created_by=None, **kwargs):
        if created_by is None:
            created_by = self.create_admin(email=f'form-admin-{TicketForm.objects.count()}@test.com')
        return TicketForm.objects.create(title=title, created_by=created_by, **kwargs)

    def create_attachment(self, ticket, uploaded_by=None, **kwargs):
        if uploaded_by is None:
            uploaded_by = ticket.created_by
        defaults = {
            'filename': 'test.txt',
            'file_size': 100,
            'content_type': 'text/plain',
        }
        defaults.update(kwargs)
        from django.core.files.uploadedfile import SimpleUploadedFile
        if 'file' not in defaults:
            defaults['file'] = SimpleUploadedFile('test.txt', b'test content', content_type='text/plain')
        return TicketAttachment.objects.create(ticket=ticket, uploaded_by=uploaded_by, **defaults)

    def setup_board_with_columns(self, admin=None):
        """Create a board with 3 columns: To Do, In Progress, Done. Returns (board, col1, col2, col3)."""
        if admin is None:
            admin = self.create_admin(email=f'setup-admin-{Board.objects.count()}@test.com')
        board = self.create_board(name='Main Board', created_by=admin)
        col_todo = self.create_column(board, name='To Do', position=0, is_default=True, created_by=admin)
        col_progress = self.create_column(board, name='In Progress', position=1, track_time=True, created_by=admin)
        col_done = self.create_column(board, name='Done', position=2, is_closed_status=True, created_by=admin)
        return board, col_todo, col_progress, col_done
