from types import SimpleNamespace

from django.test import SimpleTestCase

from invoices.serializers import ClientSerializer


class ClientSerializerTests(SimpleTestCase):
    def test_get_phone_uses_phone_number_for_ecommerce_client(self):
        client = SimpleNamespace(
            id=1,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone_number='+995555111222',
        )

        data = ClientSerializer(client).data

        self.assertEqual(data['phone'], '+995555111222')

    def test_get_phone_falls_back_to_phone_for_legacy_objects(self):
        client = SimpleNamespace(
            id=2,
            first_name='Jane',
            last_name='Doe',
            email='jane@example.com',
            phone='+995555333444',
        )

        data = ClientSerializer(client).data

        self.assertEqual(data['phone'], '+995555333444')

    def test_get_phone_reads_custom_data_for_list_item(self):
        list_item = SimpleNamespace(
            id=3,
            label='Client from list',
            custom_data={'phone': '+995555777888', 'email': 'list@example.com'},
        )

        data = ClientSerializer(list_item).data

        self.assertEqual(data['phone'], '+995555777888')
