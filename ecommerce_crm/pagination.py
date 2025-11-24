from rest_framework.pagination import PageNumberPagination


class DynamicPageSizePagination(PageNumberPagination):
    """
    Custom pagination class that allows clients to specify page size via query parameter.

    Usage:
        ?page=2&page_size=50

    Default: 20 items per page
    Max: 100 items per page (to prevent overloading)
    """
    page_size = 20  # Default page size
    page_size_query_param = 'page_size'  # Allow client to override with ?page_size=X
    max_page_size = 100  # Maximum items per page to prevent abuse
