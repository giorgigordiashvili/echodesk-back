"""Tests for Invoice models: creation, calculations, methods, and constraints."""
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import IntegrityError
from invoices.models import (
    InvoiceSettings, Invoice, InvoiceLineItem, InvoicePayment, InvoiceTemplate,
)
from invoices.tests.conftest import InvoiceTestCase


# ============================================================================
# InvoiceSettings
# ============================================================================


class TestInvoiceSettings(InvoiceTestCase):

    def test_creation(self):
        settings = self.create_invoice_settings()
        self.assertEqual(settings.company_name, 'Test Company')
        self.assertEqual(settings.default_currency, 'GEL')

    def test_str_representation(self):
        settings = self.create_invoice_settings(company_name='Acme Corp')
        self.assertIn('Acme Corp', str(settings))

    def test_str_not_configured(self):
        settings = self.create_invoice_settings(company_name='')
        self.assertIn('Not Configured', str(settings))

    def test_get_next_invoice_number_first_invoice(self):
        settings = self.create_invoice_settings(invoice_prefix='INV', starting_number=1)
        year = timezone.now().year
        next_number = settings.get_next_invoice_number()
        self.assertEqual(next_number, f'INV-{year}-0001')

    def test_get_next_invoice_number_with_existing(self):
        settings = self.create_invoice_settings(invoice_prefix='INV', starting_number=1)
        admin = self.create_admin()
        year = timezone.now().year
        self.create_invoice(
            created_by=admin, invoice_number=f'INV-{year}-0001',
        )
        next_number = settings.get_next_invoice_number()
        self.assertEqual(next_number, f'INV-{year}-0002')

    def test_get_next_invoice_number_custom_prefix(self):
        settings = self.create_invoice_settings(invoice_prefix='FAC', starting_number=100)
        year = timezone.now().year
        next_number = settings.get_next_invoice_number()
        self.assertEqual(next_number, f'FAC-{year}-0100')

    def test_default_tax_rate(self):
        settings = self.create_invoice_settings(default_tax_rate=Decimal('18.00'))
        self.assertEqual(settings.default_tax_rate, Decimal('18.00'))

    def test_bank_accounts_json(self):
        accounts = [
            {'bank_name': 'Bank A', 'account_number': 'ACC1', 'is_default': True},
            {'bank_name': 'Bank B', 'account_number': 'ACC2', 'is_default': False},
        ]
        settings = self.create_invoice_settings(bank_accounts=accounts)
        self.assertEqual(len(settings.bank_accounts), 2)
        self.assertEqual(settings.bank_accounts[0]['bank_name'], 'Bank A')


# ============================================================================
# Invoice
# ============================================================================


class TestInvoice(InvoiceTestCase):

    def test_creation(self):
        admin = self.create_admin()
        invoice = self.create_invoice(created_by=admin)
        self.assertEqual(invoice.status, 'draft')
        self.assertIsNotNone(invoice.uuid)
        self.assertEqual(invoice.created_by, admin)

    def test_str_representation(self):
        admin = self.create_admin()
        ecom_client = self.create_ecommerce_client()
        invoice = self.create_invoice(
            created_by=admin,
            client=ecom_client,
            client_name='John Doe',
        )
        self.assertIn(invoice.invoice_number, str(invoice))
        self.assertIn('Draft', str(invoice))

    def test_calculate_totals_no_items(self):
        invoice = self.create_invoice()
        total = invoice.calculate_totals()
        self.assertEqual(total, Decimal('0.00'))
        self.assertEqual(invoice.subtotal, Decimal('0.00'))
        self.assertEqual(invoice.tax_amount, Decimal('0.00'))

    def test_calculate_totals_with_items(self):
        invoice = self.create_invoice()
        # Create line item without triggering auto-recalculate via save
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description='Service A',
            quantity=Decimal('2'),
            unit_price=Decimal('100.00'),
            tax_rate=Decimal('18.00'),
            discount_percent=Decimal('0.00'),
            item_source='manual',
        )
        # Manually calculate to test the method
        invoice.refresh_from_db()
        total = invoice.calculate_totals()
        # subtotal = 2 * 100 = 200, tax = 200 * 18/100 = 36, total = 200 + 36 = 236
        self.assertEqual(invoice.subtotal, Decimal('200.00'))
        self.assertEqual(invoice.tax_amount, Decimal('36.00'))
        self.assertEqual(total, Decimal('236.00'))

    def test_calculate_totals_with_discount(self):
        invoice = self.create_invoice(discount_amount=Decimal('10.00'))
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description='Service',
            quantity=Decimal('1'),
            unit_price=Decimal('100.00'),
            tax_rate=Decimal('0.00'),
            discount_percent=Decimal('0.00'),
            item_source='manual',
        )
        invoice.refresh_from_db()
        total = invoice.calculate_totals()
        # subtotal=100, tax=0, discount=10, total=90
        self.assertEqual(total, Decimal('90.00'))

    def test_calculate_totals_with_line_discount(self):
        invoice = self.create_invoice()
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description='Service',
            quantity=Decimal('1'),
            unit_price=Decimal('200.00'),
            tax_rate=Decimal('10.00'),
            discount_percent=Decimal('50.00'),
            item_source='manual',
        )
        invoice.refresh_from_db()
        total = invoice.calculate_totals()
        # line_subtotal=200, discount_amount=100, taxable_amount=100,
        # tax_amount=10, line_total=100, subtotal=100, total=100+10=110
        self.assertEqual(invoice.subtotal, Decimal('100.00'))
        self.assertEqual(invoice.tax_amount, Decimal('10.00'))
        self.assertEqual(total, Decimal('110.00'))

    def test_get_balance(self):
        invoice = self.create_invoice(
            total=Decimal('200.00'), paid_amount=Decimal('50.00'),
        )
        self.assertEqual(invoice.get_balance(), Decimal('150.00'))

    def test_get_balance_fully_paid(self):
        invoice = self.create_invoice(
            total=Decimal('200.00'), paid_amount=Decimal('200.00'),
        )
        self.assertEqual(invoice.get_balance(), Decimal('0.00'))

    def test_is_overdue_true(self):
        invoice = self.create_invoice(
            status='sent',
            due_date=timezone.now().date() - timedelta(days=5),
        )
        self.assertTrue(invoice.is_overdue())

    def test_is_overdue_false_not_due_yet(self):
        invoice = self.create_invoice(
            status='sent',
            due_date=timezone.now().date() + timedelta(days=5),
        )
        self.assertFalse(invoice.is_overdue())

    def test_is_overdue_false_draft(self):
        invoice = self.create_invoice(
            status='draft',
            due_date=timezone.now().date() - timedelta(days=5),
        )
        self.assertFalse(invoice.is_overdue())

    def test_is_overdue_false_paid(self):
        invoice = self.create_invoice(
            status='paid',
            due_date=timezone.now().date() - timedelta(days=5),
        )
        self.assertFalse(invoice.is_overdue())

    def test_is_overdue_false_cancelled(self):
        invoice = self.create_invoice(
            status='cancelled',
            due_date=timezone.now().date() - timedelta(days=5),
        )
        self.assertFalse(invoice.is_overdue())

    def test_mark_as_paid(self):
        invoice = self.create_invoice(
            status='sent', total=Decimal('500.00'),
        )
        invoice.mark_as_paid()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'paid')
        self.assertEqual(invoice.paid_amount, Decimal('500.00'))
        self.assertIsNotNone(invoice.paid_date)

    def test_update_payment_status_fully_paid(self):
        invoice = self.create_invoice(
            status='sent', total=Decimal('100.00'), paid_amount=Decimal('100.00'),
        )
        invoice.update_payment_status()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'paid')

    def test_update_payment_status_partially_paid(self):
        invoice = self.create_invoice(
            status='sent', total=Decimal('100.00'), paid_amount=Decimal('50.00'),
        )
        invoice.update_payment_status()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'partially_paid')

    def test_update_payment_status_overdue(self):
        invoice = self.create_invoice(
            status='sent',
            total=Decimal('100.00'),
            paid_amount=Decimal('0.00'),
            due_date=timezone.now().date() - timedelta(days=5),
        )
        invoice.update_payment_status()
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'overdue')

    def test_unique_invoice_number(self):
        admin = self.create_admin()
        self.create_invoice(created_by=admin, invoice_number='INV-2026-0001')
        with self.assertRaises(IntegrityError):
            self.create_invoice(created_by=admin, invoice_number='INV-2026-0001')


# ============================================================================
# InvoiceLineItem
# ============================================================================


class TestInvoiceLineItem(InvoiceTestCase):

    def test_creation(self):
        invoice = self.create_invoice()
        item = self.create_line_item(invoice)
        self.assertEqual(item.description, 'Test Service')
        self.assertEqual(item.invoice, invoice)

    def test_str_representation(self):
        invoice = self.create_invoice()
        item = self.create_line_item(invoice, description='Widget', quantity=Decimal('3'))
        self.assertEqual(str(item), 'Widget x 3')

    def test_line_subtotal(self):
        invoice = self.create_invoice()
        item = self.create_line_item(
            invoice, quantity=Decimal('3'), unit_price=Decimal('50.00'),
        )
        self.assertEqual(item.line_subtotal, Decimal('150.00'))

    def test_discount_amount(self):
        invoice = self.create_invoice()
        item = self.create_line_item(
            invoice,
            quantity=Decimal('1'),
            unit_price=Decimal('200.00'),
            discount_percent=Decimal('10.00'),
        )
        self.assertEqual(item.discount_amount, Decimal('20.00'))

    def test_taxable_amount(self):
        invoice = self.create_invoice()
        item = self.create_line_item(
            invoice,
            quantity=Decimal('1'),
            unit_price=Decimal('200.00'),
            discount_percent=Decimal('10.00'),
        )
        # 200 - 20 discount = 180
        self.assertEqual(item.taxable_amount, Decimal('180.00'))

    def test_tax_amount(self):
        invoice = self.create_invoice()
        item = self.create_line_item(
            invoice,
            quantity=Decimal('1'),
            unit_price=Decimal('100.00'),
            tax_rate=Decimal('18.00'),
            discount_percent=Decimal('0.00'),
        )
        # taxable=100, tax=18
        self.assertEqual(item.tax_amount, Decimal('18.00'))

    def test_line_total(self):
        invoice = self.create_invoice()
        item = self.create_line_item(
            invoice,
            quantity=Decimal('2'),
            unit_price=Decimal('100.00'),
            discount_percent=Decimal('10.00'),
        )
        # subtotal=200, discount=20, taxable/line_total=180
        self.assertEqual(item.line_total, Decimal('180.00'))

    def test_save_updates_invoice_totals(self):
        invoice = self.create_invoice()
        self.create_line_item(
            invoice,
            quantity=Decimal('1'),
            unit_price=Decimal('100.00'),
            tax_rate=Decimal('18.00'),
            discount_percent=Decimal('0.00'),
        )
        invoice.refresh_from_db()
        # Line item save triggers invoice.calculate_totals() and save
        self.assertEqual(invoice.subtotal, Decimal('100.00'))
        self.assertEqual(invoice.tax_amount, Decimal('18.00'))
        self.assertEqual(invoice.total, Decimal('118.00'))


# ============================================================================
# InvoicePayment
# ============================================================================


class TestInvoicePayment(InvoiceTestCase):

    def test_creation(self):
        invoice = self.create_invoice(total=Decimal('200.00'))
        payment = self.create_payment(invoice, amount=Decimal('100.00'))
        self.assertEqual(payment.amount, Decimal('100.00'))
        self.assertEqual(payment.payment_method, 'bank_transfer')

    def test_str_representation(self):
        invoice = self.create_invoice(total=Decimal('200.00'))
        payment = self.create_payment(invoice, amount=Decimal('50.00'))
        self.assertIn('50', str(payment))
        self.assertIn(invoice.invoice_number, str(payment))

    def test_save_updates_invoice_paid_amount(self):
        invoice = self.create_invoice(total=Decimal('200.00'))
        self.create_payment(invoice, amount=Decimal('80.00'))
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal('80.00'))

    def test_save_updates_status_partially_paid(self):
        invoice = self.create_invoice(total=Decimal('200.00'), status='sent')
        self.create_payment(invoice, amount=Decimal('80.00'))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'partially_paid')

    def test_save_updates_status_paid(self):
        invoice = self.create_invoice(total=Decimal('200.00'), status='sent')
        self.create_payment(invoice, amount=Decimal('200.00'))
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'paid')

    def test_multiple_payments_sum(self):
        admin = self.create_admin()
        invoice = self.create_invoice(
            total=Decimal('300.00'), status='sent', created_by=admin,
        )
        self.create_payment(invoice, amount=Decimal('100.00'), recorded_by=admin)
        self.create_payment(invoice, amount=Decimal('100.00'), recorded_by=admin)
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal('200.00'))
        self.assertEqual(invoice.status, 'partially_paid')


# ============================================================================
# InvoiceTemplate
# ============================================================================


class TestInvoiceTemplate(InvoiceTestCase):

    def test_creation(self):
        template = self.create_invoice_template()
        self.assertEqual(template.name, 'Default Template')
        self.assertTrue(template.is_active)

    def test_str_representation(self):
        template = self.create_invoice_template(name='Modern')
        self.assertEqual(str(template), 'Modern')

    def test_str_default_marker(self):
        template = self.create_invoice_template(name='Classic', is_default=True)
        self.assertIn('(Default)', str(template))

    def test_is_default_uniqueness(self):
        """Only one template should be default."""
        admin = self.create_admin()
        t1 = self.create_invoice_template(
            name='T1', is_default=True, created_by=admin,
        )
        t2 = self.create_invoice_template(
            name='T2', is_default=True, created_by=admin,
        )
        t1.refresh_from_db()
        self.assertFalse(t1.is_default)
        self.assertTrue(t2.is_default)

    def test_supported_languages(self):
        template = self.create_invoice_template(supported_languages=['en', 'ka', 'ru'])
        self.assertEqual(len(template.supported_languages), 3)
        self.assertIn('ka', template.supported_languages)
