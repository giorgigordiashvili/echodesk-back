"""
OpenAPI schema extensions for ecommerce_crm authentication and schema generation
"""
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.generators import SchemaGenerator


class EcommerceClientJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    """
    OpenAPI extension to properly document EcommerceClientJWTAuthentication
    as a Bearer token authentication scheme.
    """
    target_class = 'ecommerce_crm.authentication.EcommerceClientJWTAuthentication'
    name = 'jwtAuth'  # Use the same name as standard JWT auth

    def get_security_definition(self, auto_schema):
        """
        Return the security definition for this authentication class.
        Uses the same Bearer JWT scheme as rest_framework_simplejwt.
        """
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }


class EcommerceClientSchemaGenerator(SchemaGenerator):
    """
    Custom schema generator that includes only ecommerce CLIENT endpoints.
    Used to create a separate API documentation page for ecommerce clients.
    Admin endpoints remain in the main API documentation.
    """
    def get_endpoints(self, request=None):
        """Filter endpoints to include only ecommerce client paths"""
        endpoints = super().get_endpoints(request)

        # Filter to include only ecommerce client endpoints
        client_endpoints = []
        for path, path_regex, method, callback in endpoints:
            # Include only paths that start with /api/ecommerce/client/
            # This excludes /api/ecommerce/admin/ endpoints
            if path.startswith('/api/ecommerce/client'):
                client_endpoints.append((path, path_regex, method, callback))

        return client_endpoints
