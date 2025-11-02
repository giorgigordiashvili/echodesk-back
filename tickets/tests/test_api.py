"""
Test cases for tickets API endpoints.
Tests CRUD operations and permissions.
"""
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from decimal import Decimal
from django.utils import timezone
from tickets.tests.test_utils import TestDataMixin
from tickets.models import (
    Board, TicketColumn, Tag, Ticket,
    ChecklistItem, TicketComment, TicketPayment
)


class BoardAPITest(APITestCase, TestDataMixin):
    """Test the Board API endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.user = self.create_test_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_boards(self):
        """Test listing boards."""
        self.create_test_board(name='Board 1', created_by=self.user)
        self.create_test_board(name='Board 2', created_by=self.user)

        url = reverse('tickets:board-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", response.data)), 2)

    def test_create_board(self):
        """Test creating a board."""
        url = reverse('tickets:board-list')
        data = {
            'name': 'New Board',
            'description': 'Test board',
            'is_default': False
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Board.objects.count(), 1)
        self.assertEqual(Board.objects.first().name, 'New Board')

    def test_retrieve_board(self):
        """Test retrieving a single board."""
        board = self.create_test_board(created_by=self.user)
        url = reverse('tickets:board-detail', args=[board.id])

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], board.name)

    def test_update_board(self):
        """Test updating a board."""
        board = self.create_test_board(name='Old Name', created_by=self.user)
        url = reverse('tickets:board-detail', args=[board.id])
        data = {'name': 'New Name'}

        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        board.refresh_from_db()
        self.assertEqual(board.name, 'New Name')

    def test_delete_board(self):
        """Test deleting a board."""
        board = self.create_test_board(created_by=self.user)
        url = reverse('tickets:board-detail', args=[board.id])

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Board.objects.count(), 0)


class TicketColumnAPITest(APITestCase, TestDataMixin):
    """Test the TicketColumn API endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.user = self.create_test_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.board = self.create_test_board(created_by=self.user)

    def test_list_columns(self):
        """Test listing columns."""
        self.create_test_column(name='To Do', board=self.board, created_by=self.user)
        self.create_test_column(name='Done', board=self.board, created_by=self.user)

        url = reverse('tickets:ticketcolumn-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", response.data)), 2)

    def test_create_column(self):
        """Test creating a column."""
        url = reverse('tickets:ticketcolumn-list')
        data = {
            'name': 'In Progress',
            'board': self.board.id,
            'color': '#FF5733',
            'position': 1
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TicketColumn.objects.count(), 1)

    def test_filter_columns_by_board(self):
        """Test filtering columns by board."""
        board2 = self.create_test_board(name='Board 2', created_by=self.user)
        self.create_test_column(name='Col 1', board=self.board, created_by=self.user)
        self.create_test_column(name='Col 2', board=board2, created_by=self.user)

        url = f"{reverse('tickets:ticketcolumn-list')}?board={self.board.id}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", response.data)), 1)


class TagAPITest(APITestCase, TestDataMixin):
    """Test the Tag API endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.user = self.create_test_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_list_tags(self):
        """Test listing tags."""
        self.create_test_tag(name='Bug', created_by=self.user)
        self.create_test_tag(name='Feature', created_by=self.user)

        url = reverse('tickets:tag-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", response.data)), 2)

    def test_create_tag(self):
        """Test creating a tag."""
        url = reverse('tickets:tag-list')
        data = {
            'name': 'Priority',
            'color': '#FF0000',
            'description': 'High priority items'
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Tag.objects.count(), 1)


class TicketAPITest(APITestCase, TestDataMixin):
    """Test the Ticket API endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.user = self.create_test_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.board = self.create_test_board(created_by=self.user)
        self.column = self.create_test_column(board=self.board, created_by=self.user)

    def test_list_tickets(self):
        """Test listing tickets."""
        self.create_test_ticket(title='Ticket 1', created_by=self.user, column=self.column)
        self.create_test_ticket(title='Ticket 2', created_by=self.user, column=self.column)

        url = reverse('tickets:ticket-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", response.data)), 2)

    def test_create_ticket(self):
        """Test creating a ticket."""
        url = reverse('tickets:ticket-list')
        data = {
            'title': 'New Ticket',
            'description': 'Test description',
            'priority': 'high',
            'column': self.column.id
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Ticket.objects.count(), 1)
        self.assertEqual(Ticket.objects.first().title, 'New Ticket')

    def test_retrieve_ticket(self):
        """Test retrieving a single ticket."""
        ticket = self.create_test_ticket(created_by=self.user, column=self.column)
        url = reverse('tickets:ticket-detail', args=[ticket.id])

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], ticket.title)

    def test_update_ticket(self):
        """Test updating a ticket."""
        ticket = self.create_test_ticket(
            title='Old Title',
            created_by=self.user,
            column=self.column
        )
        url = reverse('tickets:ticket-detail', args=[ticket.id])
        data = {'title': 'New Title'}

        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        ticket.refresh_from_db()
        self.assertEqual(ticket.title, 'New Title')

    def test_delete_ticket(self):
        """Test deleting a ticket."""
        ticket = self.create_test_ticket(created_by=self.user, column=self.column)
        url = reverse('tickets:ticket-detail', args=[ticket.id])

        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_filter_tickets_by_priority(self):
        """Test filtering tickets by priority."""
        self.create_test_ticket(priority='high', created_by=self.user, column=self.column)
        self.create_test_ticket(priority='low', created_by=self.user, column=self.column)

        url = f"{reverse('tickets:ticket-list')}?priority=high"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", response.data)), 1)

    def test_filter_tickets_by_column(self):
        """Test filtering tickets by column."""
        column2 = self.create_test_column(name='Col 2', board=self.board, created_by=self.user)
        self.create_test_ticket(column=self.column, created_by=self.user)
        self.create_test_ticket(column=column2, created_by=self.user)

        url = f"{reverse('tickets:ticket-list')}?column={self.column.id}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", response.data)), 1)


class TicketCommentAPITest(APITestCase, TestDataMixin):
    """Test the TicketComment API endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.user = self.create_test_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.board = self.create_test_board(created_by=self.user)
        self.column = self.create_test_column(board=self.board, created_by=self.user)
        self.ticket = self.create_test_ticket(created_by=self.user, column=self.column)

    def test_list_comments(self):
        """Test listing comments."""
        self.create_test_comment(ticket=self.ticket, user=self.user)
        self.create_test_comment(ticket=self.ticket, user=self.user)

        url = reverse('tickets:ticketcomment-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", response.data)), 2)

    def test_create_comment(self):
        """Test creating a comment."""
        url = reverse('tickets:ticketcomment-list')
        data = {
            'comment': 'Test comment',
            'ticket': self.ticket.id
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TicketComment.objects.count(), 1)

    def test_filter_comments_by_ticket(self):
        """Test filtering comments by ticket."""
        ticket2 = self.create_test_ticket(title='Ticket 2', created_by=self.user, column=self.column)
        self.create_test_comment(ticket=self.ticket, user=self.user)
        self.create_test_comment(ticket=ticket2, user=self.user)

        url = f"{reverse('tickets:ticketcomment-list')}?ticket={self.ticket.id}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", response.data)), 1)


class TicketPaymentAPITest(APITestCase, TestDataMixin):
    """Test the TicketPayment API endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.user = self.create_test_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.board = self.create_test_board(created_by=self.user)
        self.column = self.create_test_column(board=self.board, created_by=self.user)
        self.ticket = self.create_test_ticket(
            created_by=self.user,
            column=self.column,
            price=Decimal('200.00')
        )

    def test_list_payments(self):
        """Test listing payments."""
        self.create_test_payment(ticket=self.ticket, amount=50.00, user=self.user)
        self.create_test_payment(ticket=self.ticket, amount=100.00, user=self.user)

        url = reverse('tickets:ticketpayment-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", response.data)), 2)

    def test_create_payment(self):
        """Test creating a payment."""
        url = reverse('tickets:ticketpayment-list')
        data = {
            'ticket': self.ticket.id,
            'amount': '75.00',
            'currency': 'USD',
            'payment_method': 'card',
            'payment_reference': 'REF123'
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(TicketPayment.objects.count(), 1)

    def test_filter_payments_by_ticket(self):
        """Test filtering payments by ticket."""
        ticket2 = self.create_test_ticket(
            title='Ticket 2',
            created_by=self.user,
            column=self.column,
            price=Decimal('100.00')
        )
        self.create_test_payment(ticket=self.ticket, user=self.user)
        self.create_test_payment(ticket=ticket2, user=self.user)

        url = f"{reverse('tickets:ticketpayment-list')}?ticket={self.ticket.id}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", response.data)), 1)


class ChecklistItemAPITest(APITestCase, TestDataMixin):
    """Test the ChecklistItem API endpoints."""

    def setUp(self):
        """Set up test client and user."""
        self.user = self.create_test_user()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.board = self.create_test_board(created_by=self.user)
        self.column = self.create_test_column(board=self.board, created_by=self.user)
        self.ticket = self.create_test_ticket(created_by=self.user, column=self.column)

    def test_list_checklist_items(self):
        """Test listing checklist items."""
        self.create_test_checklist_item(text='Item 1', ticket=self.ticket, created_by=self.user)
        self.create_test_checklist_item(text='Item 2', ticket=self.ticket, created_by=self.user)

        url = reverse('tickets:checklistitem-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", response.data)), 2)

    def test_create_checklist_item(self):
        """Test creating a checklist item."""
        url = reverse('tickets:checklistitem-list')
        data = {
            'text': 'New checklist item',
            'ticket': self.ticket.id,
            'is_checked': False
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ChecklistItem.objects.count(), 1)

    def test_update_checklist_item(self):
        """Test updating a checklist item."""
        item = self.create_test_checklist_item(
            text='Old text',
            ticket=self.ticket,
            created_by=self.user,
            is_checked=False
        )
        url = reverse('tickets:checklistitem-detail', args=[item.id])
        data = {'is_checked': True}

        response = self.client.patch(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        item.refresh_from_db()
        self.assertTrue(item.is_checked)
