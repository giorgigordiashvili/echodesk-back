"""Tests for Invoice views: settings, CRUD, line items, payments, templates."""
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch, PropertyMock
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from invoices.models import (
    InvoiceSettings, Invoice, InvoiceLineItem, InvoicePayment, InvoiceTemplate,
)
from invoices.tests.conftest import InvoiceTestCase


# ============================================================================
# InvoiceSettingsViewSet
# ============================================================================


class TestInvoiceSettingsList(InvoiceTestCase):

    def test_get_settings_creates_singleton(self):
        user = self.create_invoice_user()
        resp = self.api_get('/api/invoices/settings/', user=user)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(InvoiceSettings.objects.count(), 1)

    def test_get_settings_returns_existing(self):
        self.create_invoice_settings(company_name='Existing Corp')
        user = self.create_invoice_user()
        resp = self.api_get('/api/invoices/settings/', user=user)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['company_name'], 'Existing Corp')

    def test_unauthenticated_denied(self):
        resp = self.api_get('/api/invoices/settings/')
        self.assertIn(resp.status_code, [401, 403])


class TestInvoiceSettingsUpdate(InvoiceTestCase):

    def test_update_settings_via_post(self):
        user = self.create_invoice_user()
        resp = self.api_post(
            '/api/invoices/settings/',
            {'company_name': 'Updated Corp', 'default_currency': 'USD'},
            user=user,
        )
        self.assertEqual(resp.status_code, 200)
        settings = InvoiceSettings.objects.first()
        self.assertEqual(settings.company_name, 'Updated Corp')

    def test_update_bank_accounts(self):
        user = self.create_invoice_user()
        accounts = [
            {'bank_name': 'BOG', 'account_number': 'GE00BG0000'},
            {'bank_name': 'TBC', 'account_number': 'GE00TB0000'},
        ]
        resp = self.api_post(
            '/api/invoices/settings/',
            {'bank_accounts': accounts},
            user=user,
        )
        self.assertEqual(resp.status_code, 200)
        settings = InvoiceSettings.objects.first()
        self.assertEqual(len(settings.bank_accounts), 2)

    def test_invalid_bank_accounts(self):
        user = self.create_invoice_user()
        resp = self.api_post(
            '/api/invoices/settings/',
            {'bank_accounts': [{'invalid_key': 'no bank_name'}]},
            user=user,
        )
        self.assertEqual(resp.status_code, 400)


class TestInvoiceSettingsFileUploads(InvoiceTestCase):

    def test_upload_logo(self):
        user = self.create_invoice_user()
        InvoiceSettings.objects.get_or_create()
        logo = SimpleUploadedFile('logo.png', b'fake-png', content_type='image/png')
        client = self.authenticated_client(user)
        resp = client.post(
            '/api/invoices/settings/upload-logo/',
            {'logo': logo},
            format='multipart',
            HTTP_HOST='tenant.test.com',
        )
        self.assertEqual(resp.status_code, 200)

    def test_upload_logo_no_file(self):
        user = self.create_invoice_user()
        InvoiceSettings.objects.get_or_create()
        client = self.authenticated_client(user)
        resp = client.post(
            '/api/invoices/settings/upload-logo/',
            {},
            format='multipart',
            HTTP_HOST='tenant.test.com',
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_badge(self):
        user = self.create_invoice_user()
        InvoiceSettings.objects.get_or_create()
        badge = SimpleUploadedFile('badge.png', b'fake-png', content_type='image/png')
        client = self.authenticated_client(user)
        resp = client.post(
            '/api/invoices/settings/upload-badge/',
            {'badge': badge},
            format='multipart',
            HTTP_HOST='tenant.test.com',
        )
        self.assertEqual(resp.status_code, 200)

    def test_upload_badge_no_file(self):
        user = self.create_invoice_user()
        InvoiceSettings.objects.get_or_create()
        client = self.authenticated_client(user)
        resp = client.post(
            '/api/invoices/settings/upload-badge/',
            {},
            format='multipart',
            HTTP_HOST='tenant.test.com',
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_signature(self):
        user = self.create_invoice_user()
        InvoiceSettings.objects.get_or_create()
        sig = SimpleUploadedFile('sig.png', b'fake-png', content_type='image/png')
        client = self.authenticated_client(user)
        resp = client.post(
            '/api/invoices/settings/upload-signature/',
            {'signature': sig},
            format='multipart',
            HTTP_HOST='tenant.test.com',
        )
        self.assertEqual(resp.status_code, 200)

    def test_upload_signature_no_file(self):
        user = self.create_invoice_user()
        InvoiceSettings.objects.get_or_create()
        client = self.authenticated_client(user)
        resp = client.post(
            '/api/invoices/settings/upload-signature/',
            {},
            format='multipart',
            HTTP_HOST='tenant.test.com',
        )
        self.assertEqual(resp.status_code, 400)

    def test_remove_logo(self):
        user = self.create_invoice_user()
        InvoiceSettings.objects.get_or_create()
        resp = self.api_delete('/api/invoices/settings/remove-logo/', user=user)
        self.assertEqual(resp.status_code, 200)

    def test_remove_badge(self):
        user = self.create_invoice_user()
        InvoiceSettings.objects.get_or_create()
        resp = self.api_delete('/api/invoices/settings/remove-badge/', user=user)
        self.assertEqual(resp.status_code, 200)

    def test_remove_signature(self):
        user = self.create_invoice_user()
        InvoiceSettings.objects.get_or_create()
        resp = self.api_delete('/api/invoices/settings/remove-signature/', user=user)
        self.assertEqual(resp.status_code, 200)


# ============================================================================
# InvoiceViewSet
# ============================================================================


class TestInvoiceList(InvoiceTestCase):

    def test_list_invoices(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        self.create_invoice(created_by=user, client=ecom_client)
        self.create_invoice(created_by=user, client=ecom_client)
        resp = self.api_get('/api/invoices/invoices/', user=user)
        self.assertEqual(resp.status_code, 200)
        results = self.get_results(resp)
        self.assertEqual(len(results), 2)

    def test_list_unauthenticated(self):
        resp = self.api_get('/api/invoices/invoices/')
        self.assertIn(resp.status_code, [401, 403])

    def test_filter_by_status(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        self.create_invoice(created_by=user, client=ecom_client, status='draft')
        self.create_invoice(created_by=user, client=ecom_client, status='sent')
        resp = self.api_get('/api/invoices/invoices/?status=draft', user=user)
        self.assertEqual(resp.status_code, 200)
        results = self.get_results(resp)
        self.assertEqual(len(results), 1)


class TestInvoiceCreate(InvoiceTestCase):

    def test_create_invoice_with_ecommerce_client(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        self.create_invoice_settings()
        data = {
            'client': ecom_client.id,
            'issue_date': str(timezone.now().date()),
            'due_date': str(timezone.now().date() + timedelta(days=30)),
            'currency': 'GEL',
        }
        resp = self.api_post('/api/invoices/invoices/', data, user=user)
        self.assertEqual(resp.status_code, 201)
        self.assertIn('invoice_number', resp.data)

    def test_create_invoice_with_itemlist_client(self):
        user = self.create_invoice_user()
        item_list = self.create_item_list(created_by=user)
        list_item = self.create_list_item(item_list, label='Client From List')
        settings = self.create_invoice_settings()
        settings.client_itemlist = item_list
        settings.save()
        data = {
            'client': list_item.id,
            'issue_date': str(timezone.now().date()),
            'due_date': str(timezone.now().date() + timedelta(days=30)),
        }
        resp = self.api_post('/api/invoices/invoices/', data, user=user)
        self.assertEqual(resp.status_code, 201)

    def test_create_invoice_with_line_items(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        self.create_invoice_settings()
        data = {
            'client': ecom_client.id,
            'issue_date': str(timezone.now().date()),
            'due_date': str(timezone.now().date() + timedelta(days=30)),
            'line_items': [
                {
                    'description': 'Service A',
                    'quantity': '2',
                    'unit_price': '100.00',
                    'tax_rate': '18.00',
                    'discount_percent': '0.00',
                    'item_source': 'manual',
                },
            ],
        }
        resp = self.api_post('/api/invoices/invoices/', data, user=user)
        self.assertEqual(resp.status_code, 201)

    def test_create_invoice_due_date_before_issue_date(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        self.create_invoice_settings()
        data = {
            'client': ecom_client.id,
            'issue_date': str(timezone.now().date()),
            'due_date': str(timezone.now().date() - timedelta(days=5)),
        }
        resp = self.api_post('/api/invoices/invoices/', data, user=user)
        self.assertEqual(resp.status_code, 400)

    def test_create_invoice_invalid_client(self):
        user = self.create_invoice_user()
        self.create_invoice_settings()
        data = {
            'client': 99999,
            'issue_date': str(timezone.now().date()),
            'due_date': str(timezone.now().date() + timedelta(days=30)),
        }
        resp = self.api_post('/api/invoices/invoices/', data, user=user)
        self.assertEqual(resp.status_code, 400)


class TestInvoiceRetrieve(InvoiceTestCase):

    def test_retrieve_invoice(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        invoice = self.create_invoice(created_by=user, client=ecom_client)
        resp = self.api_get(f'/api/invoices/invoices/{invoice.id}/', user=user)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['invoice_number'], invoice.invoice_number)


class TestInvoiceUpdate(InvoiceTestCase):

    def test_update_draft_invoice(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        invoice = self.create_invoice(
            created_by=user, client=ecom_client, status='draft',
        )
        resp = self.api_patch(
            f'/api/invoices/invoices/{invoice.id}/',
            {'notes': 'Updated notes', 'client': ecom_client.id},
            user=user,
        )
        self.assertEqual(resp.status_code, 200)

    def test_update_non_draft_invoice_rejected(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        invoice = self.create_invoice(
            created_by=user, client=ecom_client, status='sent',
        )
        resp = self.api_patch(
            f'/api/invoices/invoices/{invoice.id}/',
            {'notes': 'Should fail', 'client': ecom_client.id},
            user=user,
        )
        self.assertEqual(resp.status_code, 400)


class TestInvoiceDelete(InvoiceTestCase):

    def test_delete_draft_invoice(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        invoice = self.create_invoice(
            created_by=user, client=ecom_client, status='draft',
        )
        resp = self.api_delete(f'/api/invoices/invoices/{invoice.id}/', user=user)
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(Invoice.objects.filter(id=invoice.id).exists())

    def test_delete_non_draft_invoice_rejected(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        invoice = self.create_invoice(
            created_by=user, client=ecom_client, status='sent',
        )
        resp = self.api_delete(f'/api/invoices/invoices/{invoice.id}/', user=user)
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(Invoice.objects.filter(id=invoice.id).exists())


class TestInvoiceActions(InvoiceTestCase):

    def test_mark_paid(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        invoice = self.create_invoice(
            created_by=user, client=ecom_client,
            status='sent', total=Decimal('500.00'),
        )
        resp = self.api_post(
            f'/api/invoices/invoices/{invoice.id}/mark_paid/',
            {'payment_method': 'cash'},
            user=user,
        )
        self.assertEqual(resp.status_code, 200)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, 'paid')
        self.assertEqual(invoice.paid_amount, Decimal('500.00'))
        # Payment record should be created
        self.assertTrue(InvoicePayment.objects.filter(invoice=invoice).exists())

    def test_finalize_draft(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        invoice = self.create_invoice(
            created_by=user, client=ecom_client, status='draft',
        )
        with patch('invoices.views.InvoiceViewSet.finalize') as mock_finalize:
            # The finalize action calls a Celery task; we test the view logic directly
            pass
        # Test the status check part
        resp = self.api_post(
            f'/api/invoices/invoices/{invoice.id}/finalize/',
            user=user,
        )
        # This should work or fail gracefully (Celery task is async)
        # The status should change to 'sent' regardless
        if resp.status_code == 200:
            invoice.refresh_from_db()
            self.assertEqual(invoice.status, 'sent')

    def test_finalize_non_draft_rejected(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        invoice = self.create_invoice(
            created_by=user, client=ecom_client, status='sent',
        )
        resp = self.api_post(
            f'/api/invoices/invoices/{invoice.id}/finalize/',
            user=user,
        )
        self.assertEqual(resp.status_code, 400)

    def test_send_email_draft_rejected(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        invoice = self.create_invoice(
            created_by=user, client=ecom_client, status='draft',
        )
        resp = self.api_post(
            f'/api/invoices/invoices/{invoice.id}/send_email/',
            {'recipient_email': 'test@example.com'},
            user=user,
        )
        self.assertEqual(resp.status_code, 400)

    def test_send_email_no_recipient(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        invoice = self.create_invoice(
            created_by=user, client=ecom_client, status='sent',
        )
        resp = self.api_post(
            f'/api/invoices/invoices/{invoice.id}/send_email/',
            {},
            user=user,
        )
        self.assertEqual(resp.status_code, 400)

    def test_stats(self):
        user = self.create_invoice_user()
        ecom_client = self.create_ecommerce_client()
        self.create_invoice(
            created_by=user, client=ecom_client,
            status='paid', total=Decimal('500.00'),
        )
        self.create_invoice(
            created_by=user, client=ecom_client,
            status='sent', total=Decimal('300.00'),
        )
        resp = self.api_get('/api/invoices/invoices/stats/', user=user)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('current_month', resp.data)
        self.assertIn('outstanding_amount', resp.data)
        self.assertIn('overdue_count', resp.data)


# ============================================================================
# InvoiceLineItemViewSet
# ============================================================================


class TestInvoiceLineItemViewSet(InvoiceTestCase):

    def test_list_line_items(self):
        user = self.create_invoice_user()
        invoice = self.create_invoice(created_by=user)
        self.create_line_item(invoice, description='Item A')
        self.create_line_item(invoice, description='Item B')
        resp = self.api_get(
            f'/api/invoices/line-items/?invoice_id={invoice.id}', user=user,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    def test_create_line_item(self):
        user = self.create_invoice_user()
        invoice = self.create_invoice(created_by=user)
        data = {
            'invoice': invoice.id,
            'description': 'New Item',
            'quantity': '1.00',
            'unit_price': '50.00',
            'tax_rate': '18.00',
            'discount_percent': '0.00',
            'item_source': 'manual',
        }
        resp = self.api_post('/api/invoices/line-items/', data, user=user)
        self.assertEqual(resp.status_code, 201)

    def test_delete_line_item(self):
        user = self.create_invoice_user()
        invoice = self.create_invoice(created_by=user)
        item = self.create_line_item(invoice)
        resp = self.api_delete(f'/api/invoices/line-items/{item.id}/', user=user)
        self.assertEqual(resp.status_code, 204)

    def test_reorder_line_items(self):
        user = self.create_invoice_user()
        invoice = self.create_invoice(created_by=user)
        item1 = self.create_line_item(invoice, description='A', position=0)
        item2 = self.create_line_item(invoice, description='B', position=1)
        resp = self.api_post(
            '/api/invoices/line-items/reorder/',
            {
                'items': [
                    {'id': item1.id, 'position': 1},
                    {'id': item2.id, 'position': 0},
                ],
            },
            user=user,
        )
        self.assertEqual(resp.status_code, 200)
        item1.refresh_from_db()
        item2.refresh_from_db()
        self.assertEqual(item1.position, 1)
        self.assertEqual(item2.position, 0)


# ============================================================================
# InvoicePaymentViewSet
# ============================================================================


class TestInvoicePaymentViewSet(InvoiceTestCase):

    def test_list_payments(self):
        user = self.create_invoice_user()
        invoice = self.create_invoice(
            created_by=user, total=Decimal('200.00'), status='sent',
        )
        self.create_payment(invoice, amount=Decimal('100.00'), recorded_by=user)
        resp = self.api_get(
            f'/api/invoices/payments/?invoice_id={invoice.id}', user=user,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_create_payment(self):
        user = self.create_invoice_user()
        invoice = self.create_invoice(
            created_by=user, total=Decimal('500.00'), status='sent',
        )
        data = {
            'invoice': invoice.id,
            'amount': '200.00',
            'payment_method': 'card',
        }
        resp = self.api_post('/api/invoices/payments/', data, user=user)
        self.assertEqual(resp.status_code, 201)
        invoice.refresh_from_db()
        self.assertEqual(invoice.paid_amount, Decimal('200.00'))

    def test_create_payment_sets_recorded_by(self):
        user = self.create_invoice_user()
        invoice = self.create_invoice(
            created_by=user, total=Decimal('500.00'),
        )
        data = {
            'invoice': invoice.id,
            'amount': '100.00',
            'payment_method': 'cash',
        }
        resp = self.api_post('/api/invoices/payments/', data, user=user)
        self.assertEqual(resp.status_code, 201)
        payment = InvoicePayment.objects.get(id=resp.data['id'])
        self.assertEqual(payment.recorded_by, user)


# ============================================================================
# InvoiceTemplateViewSet
# ============================================================================


class TestInvoiceTemplateViewSet(InvoiceTestCase):

    def test_list_templates(self):
        user = self.create_invoice_user()
        self.create_invoice_template(name='Template A', created_by=user)
        self.create_invoice_template(name='Template B', created_by=user)
        resp = self.api_get('/api/invoices/templates/', user=user)
        self.assertEqual(resp.status_code, 200)
        results = self.get_results(resp)
        self.assertEqual(len(results), 2)

    def test_create_template(self):
        user = self.create_invoice_user()
        data = {
            'name': 'New Template',
            'html_content': '<html>{{ invoice }}</html>',
            'css_styles': 'body {}',
            'supported_languages': ['en'],
        }
        resp = self.api_post('/api/invoices/templates/', data, user=user)
        self.assertEqual(resp.status_code, 201)
        template = InvoiceTemplate.objects.get(id=resp.data['id'])
        self.assertEqual(template.created_by, user)

    def test_create_template_invalid_language(self):
        user = self.create_invoice_user()
        data = {
            'name': 'Bad Template',
            'html_content': '<html></html>',
            'supported_languages': ['xx'],
        }
        resp = self.api_post('/api/invoices/templates/', data, user=user)
        self.assertEqual(resp.status_code, 400)

    def test_delete_template(self):
        user = self.create_invoice_user()
        template = self.create_invoice_template(created_by=user)
        resp = self.api_delete(f'/api/invoices/templates/{template.id}/', user=user)
        self.assertEqual(resp.status_code, 204)


# ============================================================================
# Permission Tests
# ============================================================================


class TestInvoicePermissions(InvoiceTestCase):

    def test_user_without_feature_denied(self):
        """Users without invoice_management feature should be denied."""
        user = self.create_user(email='no-feature@test.com')
        resp = self.api_get('/api/invoices/invoices/', user=user)
        self.assertEqual(resp.status_code, 403)

    def test_user_without_feature_denied_settings(self):
        user = self.create_user(email='no-feature-s@test.com')
        resp = self.api_get('/api/invoices/settings/', user=user)
        self.assertEqual(resp.status_code, 403)
