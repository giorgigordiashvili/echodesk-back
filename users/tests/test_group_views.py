"""
Tests for TenantGroupViewSet and legacy GroupViewSet.
Endpoints under /api/tenant-groups/ and /api/groups/.
"""
from django.contrib.auth import get_user_model
from rest_framework import status

from users.models import TenantGroup
from users.tests.conftest import EchoDeskTenantTestCase

User = get_user_model()

TENANT_GROUPS_URL = '/api/tenant-groups/'
GROUPS_URL = '/api/groups/'


def tg_detail_url(group_id):
    return f'{TENANT_GROUPS_URL}{group_id}/'


def g_detail_url(group_id):
    return f'{GROUPS_URL}{group_id}/'


class TestTenantGroupCRUD(EchoDeskTenantTestCase):
    """Tests for TenantGroupViewSet CRUD operations."""

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin()
        self.agent = self.create_user(email='grpagent@test.com')

    def test_list_tenant_groups(self):
        self.create_tenant_group(name='Group A')
        self.create_tenant_group(name='Group B')
        resp = self.api_get(TENANT_GROUPS_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(resp.data), 2)

    def test_create_tenant_group_as_admin(self):
        resp = self.api_post(TENANT_GROUPS_URL, {
            'name': 'New Group',
            'description': 'Test group',
        }, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(TenantGroup.objects.filter(name='New Group').exists())

    def test_create_tenant_group_as_agent_denied(self):
        resp = self.api_post(TENANT_GROUPS_URL, {
            'name': 'Blocked Group',
        }, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_duplicate_name(self):
        """BUG 3 regression: duplicate name returns 400, not 500."""
        self.create_tenant_group(name='Duplicate')
        resp = self.api_post(TENANT_GROUPS_URL, {
            'name': 'Duplicate',
        }, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', resp.data)

    def test_update_tenant_group(self):
        group = self.create_tenant_group(name='Updatable')
        resp = self.api_patch(
            tg_detail_url(group.id),
            {'name': 'Updated Name'},
            user=self.admin,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        group.refresh_from_db()
        self.assertEqual(group.name, 'Updated Name')

    def test_delete_tenant_group(self):
        group = self.create_tenant_group(name='Deletable')
        gid = group.id
        resp = self.api_delete(tg_detail_url(gid), user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TenantGroup.objects.filter(id=gid).exists())


class TestTenantGroupMembers(EchoDeskTenantTestCase):
    """Tests for add_users / remove_users / members actions."""

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin()
        self.agent = self.create_user(email='member@test.com')
        self.group = self.create_tenant_group(name='Members Group')

    def test_add_users_to_group(self):
        resp = self.api_post(
            f'{tg_detail_url(self.group.id)}add_users/',
            {'user_ids': [self.agent.id]},
            user=self.admin,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(self.group, self.agent.tenant_groups.all())

    def test_add_users_empty_list_returns_400(self):
        resp = self.api_post(
            f'{tg_detail_url(self.group.id)}add_users/',
            {'user_ids': []},
            user=self.admin,
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remove_users_from_group(self):
        self.agent.tenant_groups.add(self.group)
        resp = self.api_post(
            f'{tg_detail_url(self.group.id)}remove_users/',
            {'user_ids': [self.agent.id]},
            user=self.admin,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.group, self.agent.tenant_groups.all())

    def test_add_users_no_permission_denied(self):
        resp = self.api_post(
            f'{tg_detail_url(self.group.id)}add_users/',
            {'user_ids': [self.admin.id]},
            user=self.agent,
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_group_members(self):
        self.agent.tenant_groups.add(self.group)
        resp = self.api_get(
            f'{tg_detail_url(self.group.id)}members/',
            user=self.admin,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['members'][0]['email'], self.agent.email)


class TestAvailableFeatures(EchoDeskTenantTestCase):
    """Tests for available_features action."""

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin()

    def test_available_features_returns_categories(self):
        resp = self.api_get(
            f'{TENANT_GROUPS_URL}available_features/',
            user=self.admin,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('categories', resp.data)


class TestLegacyGroupViewSet(EchoDeskTenantTestCase):
    """Tests for GroupViewSet (legacy Django auth groups)."""

    def setUp(self):
        super().setUp()
        self.admin = self.create_admin()
        self.agent = self.create_user(email='legacyagent@test.com')

    def test_list_groups(self):
        resp = self.api_get(GROUPS_URL, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_create_group_permission_check(self):
        """Agent without manage_groups should be denied."""
        resp = self.api_post(GROUPS_URL, {'name': 'Blocked'}, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_group_as_admin(self):
        resp = self.api_post(GROUPS_URL, {'name': 'Admin Group'}, user=self.admin)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_add_users_returns_deprecated_error(self):
        from django.contrib.auth.models import Group
        group = Group.objects.create(name='DeprecatedGroup')
        resp = self.api_post(
            f'{g_detail_url(group.id)}add_users/',
            {'user_ids': [self.agent.id]},
            user=self.agent,
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('deprecated', resp.data['error'].lower())

    def test_remove_users_returns_deprecated_error(self):
        from django.contrib.auth.models import Group
        group = Group.objects.create(name='DeprecatedGroup2')
        resp = self.api_post(
            f'{g_detail_url(group.id)}remove_users/',
            {'user_ids': [self.agent.id]},
            user=self.agent,
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('deprecated', resp.data['error'].lower())
