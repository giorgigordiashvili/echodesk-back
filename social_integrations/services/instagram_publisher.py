import logging
import time
import requests as http_requests
from django.conf import settings
from social_integrations.models import InstagramAccountConnection

logger = logging.getLogger(__name__)


class InstagramPublisher:
    def __init__(self):
        self.api_version = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_API_VERSION', 'v23.0')

    def publish(self, post) -> str:
        """Publish a post to all active Instagram accounts with publishing permission.
        Returns the media ID from the first successful publish.
        """
        accounts = InstagramAccountConnection.objects.filter(
            is_active=True,
            facebook_page__is_active=True,
            facebook_page__has_publishing_permission=True,
        ).select_related('facebook_page')

        if not accounts.exists():
            raise ValueError("No Instagram accounts with publishing permission found")

        if not post.image_url:
            raise ValueError("Instagram posts require an image URL")

        last_media_id = None
        errors = []

        for account in accounts:
            try:
                media_id = self._publish_to_account(account, post)
                last_media_id = media_id
                logger.info(f"Published to Instagram @{account.username}: {media_id}")
            except Exception as e:
                errors.append(f"@{account.username}: {str(e)}")
                logger.error(f"Failed to publish to Instagram @{account.username}: {e}")

        if not last_media_id:
            raise ValueError(f"Failed to publish to any Instagram account: {'; '.join(errors)}")

        return last_media_id

    def _publish_to_account(self, account: InstagramAccountConnection, post) -> str:
        """Two-step Instagram publishing: create media container, then publish."""
        ig_user_id = account.instagram_account_id
        access_token = account.facebook_page.page_access_token
        caption = post.instagram_text

        # Step 1: Create media container
        create_url = f"https://graph.facebook.com/{self.api_version}/{ig_user_id}/media"
        create_params = {
            'image_url': post.image_url,
            'caption': caption,
            'access_token': access_token,
        }

        create_response = http_requests.post(create_url, data=create_params, timeout=30)
        create_data = create_response.json()

        if 'error' in create_data:
            error_msg = create_data['error'].get('message', 'Unknown error')
            raise ValueError(f"Instagram media creation error: {error_msg}")

        creation_id = create_data.get('id')
        if not creation_id:
            raise ValueError("Instagram API did not return a creation ID")

        # Wait for media processing
        self._wait_for_media_ready(ig_user_id, creation_id, access_token)

        # Step 2: Publish the container
        publish_url = f"https://graph.facebook.com/{self.api_version}/{ig_user_id}/media_publish"
        publish_params = {
            'creation_id': creation_id,
            'access_token': access_token,
        }

        publish_response = http_requests.post(publish_url, data=publish_params, timeout=30)
        publish_data = publish_response.json()

        if 'error' in publish_data:
            error_msg = publish_data['error'].get('message', 'Unknown error')
            raise ValueError(f"Instagram publish error: {error_msg}")

        return publish_data.get('id', '')

    def _wait_for_media_ready(self, ig_user_id: str, creation_id: str, access_token: str, max_retries: int = 10):
        """Poll until the media container is ready for publishing."""
        status_url = f"https://graph.facebook.com/{self.api_version}/{creation_id}"
        for i in range(max_retries):
            response = http_requests.get(status_url, params={
                'fields': 'status_code',
                'access_token': access_token,
            }, timeout=15)
            data = response.json()
            status_code = data.get('status_code')

            if status_code == 'FINISHED':
                return
            elif status_code == 'ERROR':
                raise ValueError("Instagram media container processing failed")

            time.sleep(2)

        raise ValueError("Instagram media container processing timed out")
