"""
Tests for rating statistics and public rating views.
"""
from unittest.mock import patch
from rest_framework import status
from social_integrations.tests.conftest import SocialIntegrationTestCase


class TestRatingStatistics(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.staff = self.create_user(email='rating-staff@test.com', is_staff=True)
        self.agent = self.create_user(email='rating-agent@test.com')
        self.url = '/api/social/rating-statistics/'

    def test_staff_can_view(self):
        resp = self.api_get(self.url, user=self.staff)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_non_staff_denied(self):
        """Fix 3 verification."""
        resp = self.api_get(self.url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_denied(self):
        resp = self.client.get(self.url, HTTP_HOST='tenant.test.com')
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_with_date_filters(self):
        resp = self.api_get(
            f'{self.url}?start_date=2024-01-01&end_date=2024-12-31',
            user=self.staff,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_with_ratings_data(self):
        user = self.create_user(email='rated@test.com')
        self.create_chat_rating(rated_user=user, rating=5)
        self.create_chat_rating(rated_user=user, rating=3)
        resp = self.api_get(self.url, user=self.staff)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class TestUserChatSessions(SocialIntegrationTestCase):

    def setUp(self):
        super().setUp()
        self.staff = self.create_user(email='session-staff@test.com', is_staff=True)
        self.agent = self.create_user(email='session-agent@test.com')
        self.target_user = self.create_user(email='target@test.com')

    def test_staff_can_view(self):
        url = f'/api/social/rating-statistics/user/{self.target_user.id}/'
        resp = self.api_get(url, user=self.staff)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_non_staff_denied(self):
        url = f'/api/social/rating-statistics/user/{self.target_user.id}/'
        resp = self.api_get(url, user=self.agent)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class TestPublicRatingEndpoints(SocialIntegrationTestCase):

    def test_get_rating_info_invalid_token(self):
        resp = self.client.get(
            '/api/social/public/rating/invalid_token/',
            HTTP_HOST='tenant.test.com',
        )
        self.assertIn(resp.status_code, [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST,
        ])

    def test_submit_rating_invalid_token(self):
        resp = self.client.post(
            '/api/social/public/rating/invalid_token/submit/',
            {'rating': 5},
            HTTP_HOST='tenant.test.com',
            content_type='application/json',
        )
        self.assertIn(resp.status_code, [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_400_BAD_REQUEST,
        ])
