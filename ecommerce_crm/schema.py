"""
OpenAPI schema extensions for ecommerce_crm authentication
"""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


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
