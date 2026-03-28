"""Tests for ItemListViewSet and ListItemViewSet."""
from tickets.models import ItemList, ListItem
from tickets.tests.conftest import TicketTestCase


class TestItemListCRUD(TicketTestCase):

    def test_create_item_list(self):
        admin = self.create_admin()
        resp = self.api_post('/api/item-lists/', {'title': 'Products'}, user=admin)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data['title'], 'Products')

    def test_list_item_lists(self):
        admin = self.create_admin()
        self.create_item_list(title='List A', created_by=admin)
        self.create_item_list(title='List B', created_by=admin)
        resp = self.api_get('/api/item-lists/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.get_results(resp)), 2)

    def test_retrieve_item_list(self):
        admin = self.create_admin()
        lst = self.create_item_list(title='Detail List', created_by=admin)
        resp = self.api_get(f'/api/item-lists/{lst.id}/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['title'], 'Detail List')

    def test_update_item_list(self):
        admin = self.create_admin()
        lst = self.create_item_list(title='Old', created_by=admin)
        resp = self.api_patch(f'/api/item-lists/{lst.id}/', {'title': 'New'}, user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['title'], 'New')

    def test_delete_item_list(self):
        admin = self.create_admin()
        lst = self.create_item_list(title='Del', created_by=admin)
        resp = self.api_delete(f'/api/item-lists/{lst.id}/', user=admin)
        self.assertEqual(resp.status_code, 204)

    def test_filter_by_is_active(self):
        admin = self.create_admin()
        self.create_item_list(title='Active', created_by=admin, is_active=True)
        self.create_item_list(title='Inactive', created_by=admin, is_active=False)
        resp = self.api_get('/api/item-lists/?is_active=true', user=admin)
        self.assertEqual(len(self.get_results(resp)), 1)
        self.assertEqual(self.get_results(resp)[0]['title'], 'Active')


class TestItemListActions(TicketTestCase):

    def test_root_items(self):
        admin = self.create_admin()
        lst = self.create_item_list(title='Roots', created_by=admin)
        root = self.create_list_item(lst, label='Root', created_by=admin)
        self.create_list_item(lst, label='Child', parent=root, created_by=admin)
        resp = self.api_get(f'/api/item-lists/{lst.id}/root_items/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.get_results(resp)), 1)
        self.assertEqual(self.get_results(resp)[0]['label'], 'Root')

    def test_public_lists(self):
        admin = self.create_admin()
        self.create_item_list(title='Public', created_by=admin, is_public=True)
        self.create_item_list(title='Private', created_by=admin, is_public=False)
        resp = self.api_get('/api/item-lists/public/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.get_results(resp)), 1)

    def test_public_items(self):
        admin = self.create_admin()
        lst = self.create_item_list(title='PubList', created_by=admin, is_public=True)
        self.create_list_item(lst, label='Pub Item', created_by=admin)
        resp = self.api_get(f'/api/item-lists/{lst.id}/public_items/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.get_results(resp)), 1)

    def test_public_items_non_public_list(self):
        admin = self.create_admin()
        lst = self.create_item_list(title='PrivList', created_by=admin, is_public=False)
        resp = self.api_get(f'/api/item-lists/{lst.id}/public_items/', user=admin)
        self.assertEqual(resp.status_code, 404)


class TestListItemCRUD(TicketTestCase):

    def test_create_list_item(self):
        admin = self.create_admin()
        lst = self.create_item_list(title='L', created_by=admin)
        resp = self.api_post('/api/list-items/', {
            'item_list': lst.id, 'label': 'New Item'
        }, user=admin)
        self.assertEqual(resp.status_code, 201)

    def test_list_items_filter(self):
        admin = self.create_admin()
        lst = self.create_item_list(title='L', created_by=admin)
        root = self.create_list_item(lst, label='Root', created_by=admin)
        self.create_list_item(lst, label='Child', parent=root, created_by=admin)
        resp = self.api_get(
            f'/api/list-items/?item_list={lst.id}&root_only=true', user=admin
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.get_results(resp)), 1)


class TestListItemActions(TicketTestCase):

    def test_children(self):
        admin = self.create_admin()
        lst = self.create_item_list(title='L', created_by=admin)
        root = self.create_list_item(lst, label='Root', created_by=admin)
        self.create_list_item(lst, label='Child 1', parent=root, created_by=admin)
        self.create_list_item(lst, label='Child 2', parent=root, created_by=admin)
        resp = self.api_get(f'/api/list-items/{root.id}/children/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.get_results(resp)), 2)

    def test_all_descendants(self):
        admin = self.create_admin()
        lst = self.create_item_list(title='L', created_by=admin)
        root = self.create_list_item(lst, label='Root', created_by=admin)
        child = self.create_list_item(lst, label='Child', parent=root, created_by=admin)
        self.create_list_item(lst, label='Grandchild', parent=child, created_by=admin)
        resp = self.api_get(f'/api/list-items/{root.id}/all_descendants/', user=admin)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.get_results(resp)), 2)

    def test_reorder(self):
        admin = self.create_admin()
        lst = self.create_item_list(title='L', created_by=admin)
        i1 = self.create_list_item(lst, label='I1', created_by=admin)
        i2 = self.create_list_item(lst, label='I2', created_by=admin)
        resp = self.api_patch(f'/api/list-items/{i1.id}/reorder/', {
            'position': 2
        }, user=admin)
        self.assertEqual(resp.status_code, 200)
