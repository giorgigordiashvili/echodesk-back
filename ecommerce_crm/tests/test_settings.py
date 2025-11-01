"""
Test settings - Use SQLite for testing instead of production PostgreSQL
"""
from amanati_crm.settings import *

# Override database to use SQLite for tests
DATABASES = {
    'default': {
        'ENGINE': 'tenant_schemas.postgresql_backend',
        'NAME': ':memory:',  # In-memory database
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}

# Disable tenant-specific features for unit tests
# For testing individual components without full tenant context
TENANT_MODEL = "tenants.Client"
TENANT_DOMAIN_MODEL = "tenants.Domain"

# Use console email backend for testing
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Faster password hashing for tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# Disable debugging in tests
DEBUG = False
TEMPLATE_DEBUG = False

# Disable some middleware for faster tests
MIDDLEWARE = [m for m in MIDDLEWARE if 'Debug' not in m]
