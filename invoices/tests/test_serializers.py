"""Tests for Invoice serializers: field presence, validation, read-only enforcement."""
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from invoices.models import (
    InvoiceSettings, Invoice, InvoiceLineItem, InvoicePayment, InvoiceTemplate,
)
from invoices.serializers import (
    InvoiceSettingsSerializer,
    InvoiceListSerializer,
    InvoiceDetailSerializer,
    InvoiceCreateUpdateSerializer,
    InvoiceLineItemSerializer,
    InvoicePaymentSerializer,
    InvoiceTemplateSerializer,
    ClientSerializer,
    ListItemMaterialSerializer,
)
from invoices.tests.conftest import InvoiceTestCase


# ============================================================================
# InvoiceSettingsSerializer
# ============================================================================


class TestInvoiceSettingsSerializer(InvoiceTestCase):

    def test_all_fields_present(self):
        settings = self.create_invoice_settings()
        serializer = InvoiceSettingsSerializer(settings)
        data = serializer.data
        expected_fields = [
            'id', 'company_name', 'tax_id', 'registration_number', 'address',
            'phone', 'email', 'website', 'logo', 'badge', 'signature',
            'invoice_prefix', 'starting_number', 'default_currency',
            'default_tax_rate', 'default_due_days', 'bank_accounts',
            'client_itemlist', 'materials_itemlist', 'email_from',
            'email_from_name', 'email_cc', 'email_subject_template',
            'email_message_template', 'footer_text', 'default_terms',
            'created_at', 'updated_at', 'client_itemlist_details',
        ]
        for field in expected_fields:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_read_only_fields(self):
        settings = self.create_invoice_settings()
        serializer = InvoiceSettingsSerializer(settings)
        read_only = serializer.Meta.read_only_fields
        self.assertIn('created_at', read_only)
        self.assertIn('updated_at', read_only)

    def test_valid_bank_accounts(self):
        accounts = [
            {'bank_name': 'BOG', 'account_number': 'GE00BG0000'},
        ]
        settings = self.create_invoice_settings()
        serializer = InvoiceSettingsSerializer(
            settings, data={'bank_accounts': accounts}, partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_bank_accounts_not_list(self):
        settings = self.create_invoice_settings()
        serializer = InvoiceSettingsSerializer(
            settings, data={'bank_accounts': 'not-a-list'}, partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('bank_accounts', serializer.errors)

    def test_invalid_bank_accounts_missing_fields(self):
        settings = self.create_invoice_settings()
        serializer = InvoiceSettingsSerializer(
            settings,
            data={'bank_accounts': [{'iban': 'only-iban'}]},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())

    def test_client_itemlist_details_present(self):
        admin = self.create_admin()
        item_list = self.create_item_list(created_by=admin)
        settings = self.create_invoice_settings()
        settings.client_itemlist = item_list
        settings.save()
        serializer = InvoiceSettingsSerializer(settings)
        details = serializer.data['client_itemlist_details']
        self.assertIsNotNone(details)
        self.assertEqual(details['id'], item_list.id)
        self.assertEqual(details['title'], item_list.title)

    def test_client_itemlist_details_null_when_unset(self):
        settings = self.create_invoice_settings()
        serializer = InvoiceSettingsSerializer(settings)
        self.assertIsNone(serializer.data['client_itemlist_details'])


# ============================================================================
# InvoiceLineItemSerializer
# ============================================================================


class TestInvoiceLineItemSerializer(InvoiceTestCase):

    def test_all_fields_present(self):
        invoice = self.create_invoice()
        item = self.create_line_item(invoice)
        serializer = InvoiceLineItemSerializer(item)
        data = serializer.data
        expected = [
            'id', 'item_source', 'product', 'list_item', 'description',
            'quantity', 'unit', 'unit_price', 'tax_rate', 'discount_percent',
            'position', 'created_at', 'updated_at',
            'line_subtotal', 'discount_amount', 'taxable_amount',
            'tax_amount', 'line_total', 'product_name', 'list_item_label',
        ]
        for field in expected:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_computed_fields_read_only(self):
        invoice = self.create_invoice()
        item = self.create_line_item(
            invoice,
            quantity=Decimal('2'), unit_price=Decimal('50.00'),
            tax_rate=Decimal('10.00'), discount_percent=Decimal('5.00'),
        )
        serializer = InvoiceLineItemSerializer(item)
        data = serializer.data
        # line_subtotal = 2*50 = 100, discount = 5%, taxable = 95, tax = 9.5, line_total = 95
        self.assertEqual(Decimal(data['line_subtotal']), Decimal('100.00'))
        self.assertEqual(Decimal(data['discount_amount']), Decimal('5.00'))
        self.assertEqual(Decimal(data['taxable_amount']), Decimal('95.00'))
        self.assertEqual(Decimal(data['tax_amount']), Decimal('9.50'))
        self.assertEqual(Decimal(data['line_total']), Decimal('95.00'))

    def test_validation_manual_requires_description(self):
        invoice = self.create_invoice()
        serializer = InvoiceLineItemSerializer(data={
            'item_source': 'manual',
            'description': '',
            'quantity': '1',
            'unit_price': '100.00',
        })
        self.assertFalse(serializer.is_valid())

    def test_validation_product_source_requires_product(self):
        serializer = InvoiceLineItemSerializer(data={
            'item_source': 'product',
            'description': 'Prod',
            'quantity': '1',
            'unit_price': '100.00',
        })
        self.assertFalse(serializer.is_valid())

    def test_validation_list_item_source_requires_list_item(self):
        serializer = InvoiceLineItemSerializer(data={
            'item_source': 'list_item',
            'description': 'Mat',
            'quantity': '1',
            'unit_price': '100.00',
        })
        self.assertFalse(serializer.is_valid())

    def test_valid_manual_entry(self):
        invoice = self.create_invoice()
        serializer = InvoiceLineItemSerializer(data={
            'item_source': 'manual',
            'description': 'Consulting',
            'quantity': '5',
            'unit_price': '200.00',
            'tax_rate': '18.00',
            'discount_percent': '0.00',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)


# ============================================================================
# InvoicePaymentSerializer
# ============================================================================


class TestInvoicePaymentSerializer(InvoiceTestCase):

    def test_all_fields_present(self):
        admin = self.create_admin()
        invoice = self.create_invoice(created_by=admin, total=Decimal('200.00'))
        payment = self.create_payment(invoice, recorded_by=admin, amount=Decimal('100.00'))
        serializer = InvoicePaymentSerializer(payment)
        data = serializer.data
        expected = [
            'id', 'invoice', 'payment_date', 'amount', 'payment_method',
            'reference_number', 'notes', 'recorded_by', 'created_at',
            'updated_at', 'recorded_by_name',
        ]
        for field in expected:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_read_only_fields(self):
        serializer = InvoicePaymentSerializer()
        read_only = serializer.Meta.read_only_fields
        self.assertIn('recorded_by', read_only)
        self.assertIn('created_at', read_only)
        self.assertIn('updated_at', read_only)

    def test_amount_and_method_serialized(self):
        admin = self.create_admin()
        invoice = self.create_invoice(created_by=admin, total=Decimal('500.00'))
        payment = self.create_payment(
            invoice, recorded_by=admin, amount=Decimal('250.00'),
            payment_method='card',
        )
        serializer = InvoicePaymentSerializer(payment)
        self.assertEqual(Decimal(serializer.data['amount']), Decimal('250.00'))
        self.assertEqual(serializer.data['payment_method'], 'card')


# ============================================================================
# InvoiceListSerializer
# ============================================================================


class TestInvoiceListSerializer(InvoiceTestCase):

    def test_expected_fields(self):
        ecom_client = self.create_ecommerce_client()
        invoice = self.create_invoice(client=ecom_client, total=Decimal('100.00'))
        serializer = InvoiceListSerializer(invoice)
        data = serializer.data
        expected = [
            'id', 'uuid', 'invoice_number', 'status', 'client',
            'client_name', 'issue_date', 'due_date', 'currency', 'total',
            'paid_amount', 'balance', 'is_overdue', 'line_items_count',
            'created_at',
        ]
        for field in expected:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_client_name_from_ecommerce_client(self):
        ecom_client = self.create_ecommerce_client(
            first_name='Alice', last_name='Smith',
        )
        invoice = self.create_invoice(
            client=ecom_client, client_name='Alice Smith',
        )
        serializer = InvoiceListSerializer(invoice)
        self.assertEqual(serializer.data['client_name'], 'Alice Smith')

    def test_client_name_from_itemlist(self):
        admin = self.create_admin()
        item_list = self.create_item_list(created_by=admin)
        list_item = self.create_list_item(item_list, label='ItemList Client')
        invoice = self.create_invoice(created_by=admin)
        invoice.client_itemlist_item = list_item
        invoice.save()
        serializer = InvoiceListSerializer(invoice)
        self.assertEqual(serializer.data['client_name'], 'ItemList Client')

    def test_is_overdue_serialized(self):
        invoice = self.create_invoice(
            status='sent',
            due_date=timezone.now().date() - timedelta(days=1),
        )
        serializer = InvoiceListSerializer(invoice)
        self.assertTrue(serializer.data['is_overdue'])

    def test_balance_calculation(self):
        invoice = self.create_invoice(
            total=Decimal('500.00'), paid_amount=Decimal('200.00'),
        )
        serializer = InvoiceListSerializer(invoice)
        self.assertEqual(Decimal(serializer.data['balance']), Decimal('300.00'))


# ============================================================================
# InvoiceDetailSerializer
# ============================================================================


class TestInvoiceDetailSerializer(InvoiceTestCase):

    def test_nested_line_items_included(self):
        admin = self.create_admin()
        invoice = self.create_invoice(created_by=admin)
        self.create_line_item(invoice, description='Item A')
        self.create_line_item(invoice, description='Item B')
        invoice.refresh_from_db()
        serializer = InvoiceDetailSerializer(invoice)
        self.assertEqual(len(serializer.data['line_items']), 2)

    def test_nested_payments_included(self):
        admin = self.create_admin()
        invoice = self.create_invoice(
            created_by=admin, total=Decimal('300.00'), status='sent',
        )
        self.create_payment(invoice, recorded_by=admin, amount=Decimal('100.00'))
        invoice.refresh_from_db()
        serializer = InvoiceDetailSerializer(invoice)
        self.assertEqual(len(serializer.data['payments']), 1)

    def test_read_only_fields(self):
        serializer = InvoiceDetailSerializer()
        read_only = serializer.Meta.read_only_fields
        self.assertIn('invoice_number', read_only)
        self.assertIn('subtotal', read_only)
        self.assertIn('tax_amount', read_only)
        self.assertIn('total', read_only)
        self.assertIn('paid_amount', read_only)
        self.assertIn('uuid', read_only)
        self.assertIn('created_by', read_only)
        self.assertIn('created_at', read_only)
        self.assertIn('updated_at', read_only)

    def test_client_details_ecommerce(self):
        ecom_client = self.create_ecommerce_client(
            first_name='Bob', last_name='Jones', email='bob@test.com',
        )
        invoice = self.create_invoice(client=ecom_client, client_name='Bob Jones')
        serializer = InvoiceDetailSerializer(invoice)
        details = serializer.data['client_details']
        self.assertEqual(details['first_name'], 'Bob')
        self.assertEqual(details['last_name'], 'Jones')
        self.assertEqual(details['email'], 'bob@test.com')

    def test_client_details_itemlist(self):
        admin = self.create_admin()
        item_list = self.create_item_list(created_by=admin)
        list_item = self.create_list_item(
            item_list, label='Corp Client',
            custom_data={'email': 'corp@test.com', 'phone': '+1234'},
        )
        invoice = self.create_invoice(created_by=admin)
        invoice.client_itemlist_item = list_item
        invoice.save()
        serializer = InvoiceDetailSerializer(invoice)
        details = serializer.data['client_details']
        self.assertEqual(details['full_name'], 'Corp Client')
        self.assertEqual(details['email'], 'corp@test.com')

    def test_client_details_fallback(self):
        invoice = self.create_invoice(client_name='Fallback Name')
        serializer = InvoiceDetailSerializer(invoice)
        details = serializer.data['client_details']
        self.assertEqual(details['full_name'], 'Fallback Name')
        self.assertIsNone(details['id'])


# ============================================================================
# InvoiceCreateUpdateSerializer
# ============================================================================


class TestInvoiceCreateUpdateSerializer(InvoiceTestCase):

    def test_required_fields(self):
        serializer = InvoiceCreateUpdateSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('client', serializer.errors)

    def test_due_date_before_issue_date_invalid(self):
        ecom_client = self.create_ecommerce_client()
        self.create_invoice_settings()
        serializer = InvoiceCreateUpdateSerializer(
            data={
                'client': ecom_client.id,
                'issue_date': str(timezone.now().date()),
                'due_date': str(timezone.now().date() - timedelta(days=5)),
            },
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('due_date', serializer.errors)

    def test_valid_create_with_ecommerce_client(self):
        ecom_client = self.create_ecommerce_client()
        self.create_invoice_settings()
        serializer = InvoiceCreateUpdateSerializer(
            data={
                'client': ecom_client.id,
                'issue_date': str(timezone.now().date()),
                'due_date': str(timezone.now().date() + timedelta(days=30)),
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_client_id(self):
        self.create_invoice_settings()
        serializer = InvoiceCreateUpdateSerializer(
            data={
                'client': 99999,
                'issue_date': str(timezone.now().date()),
                'due_date': str(timezone.now().date() + timedelta(days=30)),
            },
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('client', serializer.errors)

    def test_create_generates_invoice_number(self):
        ecom_client = self.create_ecommerce_client()
        self.create_invoice_settings()
        admin = self.create_admin()
        serializer = InvoiceCreateUpdateSerializer(
            data={
                'client': ecom_client.id,
                'issue_date': str(timezone.now().date()),
                'due_date': str(timezone.now().date() + timedelta(days=30)),
            },
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        invoice = serializer.save(created_by=admin)
        year = timezone.now().year
        self.assertTrue(invoice.invoice_number.startswith(f'INV-{year}-'))

    def test_create_sets_default_currency(self):
        ecom_client = self.create_ecommerce_client()
        self.create_invoice_settings(default_currency='USD')
        admin = self.create_admin()
        serializer = InvoiceCreateUpdateSerializer(
            data={
                'client': ecom_client.id,
                'issue_date': str(timezone.now().date()),
                'due_date': str(timezone.now().date() + timedelta(days=30)),
            },
        )
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save(created_by=admin)
        self.assertEqual(invoice.currency, 'USD')

    def test_create_with_line_items(self):
        ecom_client = self.create_ecommerce_client()
        self.create_invoice_settings()
        admin = self.create_admin()
        serializer = InvoiceCreateUpdateSerializer(
            data={
                'client': ecom_client.id,
                'issue_date': str(timezone.now().date()),
                'due_date': str(timezone.now().date() + timedelta(days=30)),
                'line_items': [
                    {
                        'description': 'Widget',
                        'quantity': '3',
                        'unit_price': '10.00',
                        'tax_rate': '0.00',
                        'discount_percent': '0.00',
                        'item_source': 'manual',
                    },
                ],
            },
        )
        serializer.is_valid(raise_exception=True)
        invoice = serializer.save(created_by=admin)
        self.assertEqual(invoice.line_items.count(), 1)
        self.assertEqual(invoice.subtotal, Decimal('30.00'))


# ============================================================================
# InvoiceTemplateSerializer
# ============================================================================


class TestInvoiceTemplateSerializer(InvoiceTestCase):

    def test_all_fields_present(self):
        admin = self.create_admin()
        template = self.create_invoice_template(created_by=admin)
        serializer = InvoiceTemplateSerializer(template)
        data = serializer.data
        expected = [
            'id', 'name', 'description', 'html_content', 'css_styles',
            'is_default', 'is_active', 'supported_languages',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
        ]
        for field in expected:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_read_only_fields(self):
        serializer = InvoiceTemplateSerializer()
        read_only = serializer.Meta.read_only_fields
        self.assertIn('created_by', read_only)
        self.assertIn('created_at', read_only)
        self.assertIn('updated_at', read_only)

    def test_valid_supported_languages(self):
        serializer = InvoiceTemplateSerializer(data={
            'name': 'Test',
            'html_content': '<html></html>',
            'supported_languages': ['en', 'ka'],
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_supported_languages(self):
        serializer = InvoiceTemplateSerializer(data={
            'name': 'Test',
            'html_content': '<html></html>',
            'supported_languages': ['xx', 'yy'],
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('supported_languages', serializer.errors)

    def test_supported_languages_not_list(self):
        serializer = InvoiceTemplateSerializer(data={
            'name': 'Test',
            'html_content': '<html></html>',
            'supported_languages': 'en',
        })
        self.assertFalse(serializer.is_valid())


# ============================================================================
# ClientSerializer
# ============================================================================


class TestClientSerializer(InvoiceTestCase):

    def test_ecommerce_client_fields(self):
        ecom_client = self.create_ecommerce_client(
            first_name='Anna', last_name='Berg', email='anna@test.com',
        )
        serializer = ClientSerializer(ecom_client)
        data = serializer.data
        self.assertEqual(data['id'], ecom_client.id)
        self.assertEqual(data['name'], 'Anna Berg')
        self.assertEqual(data['email'], 'anna@test.com')

    def test_list_item_client_fields(self):
        admin = self.create_admin()
        item_list = self.create_item_list(created_by=admin)
        list_item = self.create_list_item(
            item_list, label='ACME Corp',
            custom_data={'email': 'acme@test.com', 'phone': '+555'},
        )
        serializer = ClientSerializer(list_item)
        data = serializer.data
        self.assertEqual(data['id'], list_item.id)
        self.assertEqual(data['name'], 'ACME Corp')
        self.assertEqual(data['email'], 'acme@test.com')
        self.assertEqual(data['phone'], '+555')

    def test_list_item_client_empty_custom_data(self):
        admin = self.create_admin()
        item_list = self.create_item_list(created_by=admin)
        list_item = self.create_list_item(item_list, label='NoData', custom_data={})
        serializer = ClientSerializer(list_item)
        data = serializer.data
        self.assertEqual(data['email'], '')
        self.assertEqual(data['phone'], '')


# ============================================================================
# ListItemMaterialSerializer
# ============================================================================


class TestListItemMaterialSerializer(InvoiceTestCase):

    def test_fields_present(self):
        admin = self.create_admin()
        item_list = self.create_item_list(created_by=admin)
        list_item = self.create_list_item(
            item_list, label='Steel Pipe',
            custom_data={'price': 45.50, 'unit': 'meter', 'description': 'Galvanized pipe'},
        )
        serializer = ListItemMaterialSerializer(list_item)
        data = serializer.data
        expected = ['id', 'label', 'custom_data', 'price', 'unit', 'description']
        for field in expected:
            self.assertIn(field, data, f"Missing field: {field}")

    def test_price_extracted_from_custom_data(self):
        admin = self.create_admin()
        item_list = self.create_item_list(created_by=admin)
        list_item = self.create_list_item(
            item_list, label='Bolt',
            custom_data={'price': 2.50, 'unit': 'pcs'},
        )
        serializer = ListItemMaterialSerializer(list_item)
        self.assertEqual(serializer.data['price'], 2.50)
        self.assertEqual(serializer.data['unit'], 'pcs')

    def test_defaults_when_no_custom_data(self):
        admin = self.create_admin()
        item_list = self.create_item_list(created_by=admin)
        list_item = self.create_list_item(item_list, label='Plain', custom_data=None)
        serializer = ListItemMaterialSerializer(list_item)
        self.assertEqual(serializer.data['price'], 0)
        self.assertEqual(serializer.data['unit'], 'unit')
        self.assertEqual(serializer.data['description'], '')
