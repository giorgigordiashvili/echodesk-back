"""
Shared test infrastructure for invoices app tests.
Extends EchoDeskTenantTestCase with invoice-specific helpers.
"""
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from users.tests.conftest import EchoDeskTenantTestCase
from invoices.models import (
    InvoiceSettings, Invoice, InvoiceLineItem, InvoicePayment, InvoiceTemplate,
)
from tickets.models import ItemList, ListItem
from ecommerce_crm.models import EcommerceClient


class InvoiceTestCase(EchoDeskTenantTestCase):
    """
    Invoice-specific test case with factory helpers for all invoice models.
    """

    @staticmethod
    def get_results(resp):
        """Extract results from a paginated or non-paginated response."""
        if isinstance(resp.data, dict) and 'results' in resp.data:
            return resp.data['results']
        return resp.data

    # ── Invoice Settings ──

    def create_invoice_settings(self, **kwargs):
        defaults = {
            'company_name': 'Test Company',
            'tax_id': 'TAX-123',
            'invoice_prefix': 'INV',
            'starting_number': 1,
            'default_currency': 'GEL',
            'default_tax_rate': Decimal('18.00'),
            'default_due_days': 30,
            'bank_accounts': [
                {
                    'bank_name': 'Test Bank',
                    'account_number': 'GE00TB0000000000000001',
                }
            ],
        }
        defaults.update(kwargs)
        return InvoiceSettings.objects.create(**defaults)

    # ── Ecommerce Client ──

    def create_ecommerce_client(self, **kwargs):
        counter = EcommerceClient.objects.count()
        defaults = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': f'client-{counter}@test.com',
            'phone_number': f'+99555500{counter:04d}',
            'password': 'hashed_pass',
            'is_active': True,
        }
        defaults.update(kwargs)
        return EcommerceClient.objects.create(**defaults)

    # ── Item List / List Item ──

    def create_item_list(self, title='Client List', created_by=None, **kwargs):
        if created_by is None:
            created_by = self.create_admin(
                email=f'list-admin-{ItemList.objects.count()}@test.com'
            )
        defaults = {
            'is_active': True,
        }
        defaults.update(kwargs)
        return ItemList.objects.create(title=title, created_by=created_by, **defaults)

    def create_list_item(self, item_list, label='Test Item', **kwargs):
        defaults = {
            'is_active': True,
            'custom_data': {},
        }
        defaults.update(kwargs)
        return ListItem.objects.create(item_list=item_list, label=label, **defaults)

    # ── Invoice ──

    def create_invoice(self, created_by=None, client=None, **kwargs):
        if created_by is None:
            created_by = self.create_admin(
                email=f'inv-admin-{Invoice.objects.count()}@test.com'
            )
        counter = Invoice.objects.count()
        year = timezone.now().year
        defaults = {
            'invoice_number': f'INV-{year}-{counter + 1:04d}',
            'status': 'draft',
            'issue_date': timezone.now().date(),
            'due_date': timezone.now().date() + timedelta(days=30),
            'currency': 'GEL',
            'subtotal': Decimal('0.00'),
            'tax_amount': Decimal('0.00'),
            'discount_amount': Decimal('0.00'),
            'total': Decimal('0.00'),
            'paid_amount': Decimal('0.00'),
        }
        defaults.update(kwargs)

        if client is not None:
            defaults['client'] = client
            defaults.setdefault(
                'client_name',
                f'{client.first_name} {client.last_name}'.strip(),
            )

        return Invoice.objects.create(created_by=created_by, **defaults)

    # ── Line Item ──

    def create_line_item(self, invoice, **kwargs):
        defaults = {
            'description': 'Test Service',
            'quantity': Decimal('1.00'),
            'unit': 'unit',
            'unit_price': Decimal('100.00'),
            'tax_rate': Decimal('18.00'),
            'discount_percent': Decimal('0.00'),
            'item_source': 'manual',
            'position': 0,
        }
        defaults.update(kwargs)
        return InvoiceLineItem.objects.create(invoice=invoice, **defaults)

    # ── Payment ──

    def create_payment(self, invoice, recorded_by=None, **kwargs):
        if recorded_by is None:
            recorded_by = self.create_admin(
                email=f'pay-admin-{InvoicePayment.objects.count()}@test.com'
            )
        defaults = {
            'amount': Decimal('100.00'),
            'payment_method': 'bank_transfer',
            'payment_date': timezone.now(),
        }
        defaults.update(kwargs)
        return InvoicePayment.objects.create(
            invoice=invoice, recorded_by=recorded_by, **defaults
        )

    # ── Template ──

    def create_invoice_template(self, created_by=None, **kwargs):
        if created_by is None:
            created_by = self.create_admin(
                email=f'tpl-admin-{InvoiceTemplate.objects.count()}@test.com'
            )
        defaults = {
            'name': 'Default Template',
            'html_content': '<html><body>{{ invoice }}</body></html>',
            'css_styles': 'body { font-family: sans-serif; }',
            'is_default': False,
            'is_active': True,
            'supported_languages': ['en', 'ka'],
        }
        defaults.update(kwargs)
        return InvoiceTemplate.objects.create(created_by=created_by, **defaults)

    # ── Helper: set up a user that has the invoice_management feature ──

    def create_invoice_user(self, email='inv-user@test.com', **kwargs):
        """Create a user and mock has_feature to grant invoice_management."""
        user = self.create_admin(email=email)
        # Patch has_feature on the user instance to always return True
        # for tests that need feature-gated access
        original_has_feature = user.has_feature
        user.has_feature = lambda key: True
        user._original_has_feature = original_has_feature
        return user
