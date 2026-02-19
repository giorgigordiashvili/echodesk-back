from rest_framework.pagination import PageNumberPagination


class SocialMessagePagination(PageNumberPagination):
    """
    Custom pagination class for social messages with higher limits.

    Usage:
        ?page=2&page_size=200

    Default: 50 items per page
    Max: 500 items per page (for fetching conversation history)
    """
    page_size = 50  # Default page size
    page_size_query_param = 'page_size'
    max_page_size = 500  # Higher limit for message history
