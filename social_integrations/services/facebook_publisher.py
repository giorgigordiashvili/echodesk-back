import logging
import requests as http_requests
from django.conf import settings
from social_integrations.models import FacebookPageConnection

logger = logging.getLogger(__name__)


class FacebookPublisher:
    def __init__(self):
        self.api_version = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_API_VERSION', 'v23.0')

    def publish(self, post) -> str:
        """Publish a post to all active Facebook pages with publishing permission.
        Returns the post ID from the first successful publish.
        """
        pages = FacebookPageConnection.objects.filter(
            is_active=True,
            has_publishing_permission=True,
        )

        if not pages.exists():
            raise ValueError("No Facebook pages with publishing permission found")

        last_post_id = None
        errors = []

        for page in pages:
            try:
                post_id = self._publish_to_page(page, post)
                last_post_id = post_id
                logger.info(f"Published to Facebook page {page.page_name}: {post_id}")
            except Exception as e:
                errors.append(f"{page.page_name}: {str(e)}")
                logger.error(f"Failed to publish to Facebook page {page.page_name}: {e}")

        if not last_post_id:
            raise ValueError(f"Failed to publish to any Facebook page: {'; '.join(errors)}")

        return last_post_id

    def _publish_to_page(self, page: FacebookPageConnection, post) -> str:
        """Publish to a single Facebook page."""
        page_id = page.page_id
        access_token = page.page_access_token
        text = post.facebook_text

        if post.image_url:
            # Post with image
            url = f"https://graph.facebook.com/{self.api_version}/{page_id}/photos"
            params = {
                'message': text,
                'url': post.image_url,
                'access_token': access_token,
            }
        else:
            # Text-only post
            url = f"https://graph.facebook.com/{self.api_version}/{page_id}/feed"
            params = {
                'message': text,
                'access_token': access_token,
            }

        response = http_requests.post(url, data=params, timeout=30)
        data = response.json()

        if 'error' in data:
            error_msg = data['error'].get('message', 'Unknown error')
            raise ValueError(f"Facebook API error: {error_msg}")

        return data.get('id', data.get('post_id', ''))
