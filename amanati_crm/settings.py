"""
Django settings for amanati_crm project.
"""

import os
from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='your-secret-key-here')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

# Main domain configuration
MAIN_DOMAIN = config('MAIN_DOMAIN', default='echodesk.ge')
API_DOMAIN = config('API_DOMAIN', default='api.echodesk.ge')

ALLOWED_HOSTS = [
    MAIN_DOMAIN,  # Main domain for public schema
    f'.{MAIN_DOMAIN}',  # Wildcard for tenant frontend subdomains
    API_DOMAIN,  # API domain
    f'.{API_DOMAIN}',  # Wildcard for tenant API subdomains
    '.ondigitalocean.app',  # DigitalOcean app platform
    '.vercel.app',  # Vercel hosting
    'localhost',
    '127.0.0.1',
]

# CSRF trusted origins for cross-origin requests
CSRF_TRUSTED_ORIGINS = [
    f'https://{MAIN_DOMAIN}',
    f'https://*.{MAIN_DOMAIN}',
    f'https://{API_DOMAIN}',
    f'https://*.{API_DOMAIN}',
    'https://*.ondigitalocean.app',
    'https://*.vercel.app',
]

# Shared applications - available to all tenants
SHARED_APPS = [
    'tenant_schemas',  # mandatory, should always be before any django app
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'rest_framework',
    'rest_framework.authtoken',
    'drf_spectacular',
    'corsheaders',
    'channels',  # Add channels for WebSocket support
    'storages',  # For DigitalOcean Spaces file storage

    # Shared apps
    'tenants',  # This must be in SHARED_APPS
    'users',    # Add users to shared apps so public schema gets the table
    'crm',      # Move CRM to shared apps so it's available in public schema too
]

# Tenant-specific applications
TENANT_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'rest_framework',
    'rest_framework.authtoken',
    'drf_spectacular',
    'django_filters',
    'channels',  # Add channels for WebSocket support

    # Tenant-specific apps
    'users',    # Only available in tenant schemas
    'crm',      # Keep in tenant apps too for backwards compatibility
    'tickets',
    'social_integrations',
    'notifications',
    'ecommerce_crm',  # E-commerce product management
    'booking_management',  # Booking management for service-based businesses
    'leave_management',  # Employee leave and absence management
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

# Tenant model
TENANT_MODEL = "tenants.Tenant"

MIDDLEWARE = [
    'amanati_crm.middleware.EchoDeskTenantMiddleware',  # Custom tenant middleware (must be first)
    'tenants.subscription_middleware.SubscriptionMiddleware',  # Subscription feature middleware
    'amanati_crm.debug_middleware.TransactionDebugMiddleware',  # Debug transaction errors
    'amanati_crm.middleware.RequestLoggingMiddleware',  # Custom request logging middleware
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Static file serving
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'amanati_crm.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'amanati_crm.wsgi.application'

# Database
DATABASES = {
    'default': {
        'ENGINE': 'tenant_schemas.postgresql_backend',
        'NAME': config('DB_NAME', default='echodesk_db'),
        'USER': config('DB_USER', default='postgres'),
        'PASSWORD': config('DB_PASSWORD', default='password'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'OPTIONS': {
            'sslmode': 'require',
        } if config('DB_HOST', default='localhost') != 'localhost' else {},
    }
}

DATABASE_ROUTERS = (
    'tenant_schemas.routers.TenantSyncRouter',
)

# Custom user model
# User model
AUTH_USER_MODEL = 'users.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise configuration for static files
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# DigitalOcean Spaces Configuration
AWS_ACCESS_KEY_ID = config('DO_SPACES_ACCESS_KEY', default='')
AWS_SECRET_ACCESS_KEY = config('DO_SPACES_SECRET_KEY', default='')
AWS_STORAGE_BUCKET_NAME = config('DO_SPACES_BUCKET_NAME', default='echodesk-spaces')
AWS_S3_ENDPOINT_URL = config('DO_SPACES_ENDPOINT_URL', default='https://fra1.digitaloceanspaces.com')
AWS_S3_REGION_NAME = config('DO_SPACES_REGION', default='fra1')
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}
AWS_LOCATION = 'media'
AWS_DEFAULT_ACL = 'public-read'
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.{AWS_S3_REGION_NAME}.digitaloceanspaces.com'

# Use DigitalOcean Spaces for media file storage
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{AWS_LOCATION}/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
}

# Simple JWT Settings
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# Spectacular settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'EchoDesk API',
    'DESCRIPTION': 'Multi-tenant CRM system for EchoDesk',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'DEFAULT_SCHEMA_CLASS': 'amanati_crm.schema.FeatureAwareAutoSchema',
    'DEFAULT_GENERATOR_CLASS': 'amanati_crm.schema.TenantAwareSchemaGenerator',
    'PREPROCESSING_HOOKS': [
        'amanati_crm.schema.feature_based_preprocessing_hook',
    ],
    'SECURITY': [
        {
            'tokenAuth': [],
        }
    ],
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api',
}

# CORS settings - Allow wildcard subdomains for multi-tenant frontend
CORS_ALLOW_ALL_ORIGINS = True  # Temporarily allow all origins for development and testing

# If you want to be more restrictive in production, use this instead:
# CORS_ALLOW_ALL_ORIGINS = DEBUG  # Allow all in development, restrict in production

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    f"https://{MAIN_DOMAIN}",
    f"http://{MAIN_DOMAIN}",
    f"https://{API_DOMAIN}",
    f"http://{API_DOMAIN}",
]

# Allow all subdomains with regex patterns
escaped_main_domain = MAIN_DOMAIN.replace('.', r'\.')
escaped_api_domain = API_DOMAIN.replace('.', r'\.')

CORS_ALLOWED_ORIGIN_REGEXES = [
    f"https://.*\\.{escaped_main_domain}",  # *.echodesk.ge
    f"http://.*\\.{escaped_main_domain}",   # *.echodesk.ge (dev)
    f"https://.*\\.{escaped_api_domain}",   # *.api.echodesk.ge
    f"http://.*\\.{escaped_api_domain}",    # *.api.echodesk.ge (dev)
    r"https://.*\.ondigitalocean\.app",      # DigitalOcean app domains
    r"http://.*\.localhost:3000",            # Local development subdomains
]

# CORS configuration for multi-tenant setup
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_HEADERS = True
CORS_ALLOWED_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
    'x-tenant-subdomain',
    'x-tenant-domain',
    'cache-control',
]

# Allow all HTTP methods
CORS_ALLOWED_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

# Preflight cache time
CORS_PREFLIGHT_MAX_AGE = 86400

# Tenant settings
PUBLIC_SCHEMA_URLCONF = 'amanati_crm.urls_public'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '{asctime} [{levelname}] {name}: {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'debug.log',
            'formatter': 'detailed',
        },
        'request_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'requests.log',
            'formatter': 'detailed',
        },
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'] if DEBUG else ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['request_file', 'console'] if DEBUG else ['request_file'],
            'level': 'INFO',
            'propagate': False,  # Don't duplicate in django logger
        },
        'django.server': {
            'handlers': ['file', 'console'] if DEBUG else ['file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',  # Only log warnings and errors, not all SQL queries
            'propagate': False,
        },
        'channels': {
            'handlers': ['console'],
            'level': 'INFO',  # Log WebSocket connection info
            'propagate': False,
        },
        'daphne': {
            'handlers': ['console'],
            'level': 'INFO',  # Log Daphne server info
            'propagate': False,
        },
    },
}

# Frontend Configuration
FRONTEND_BASE_URL = config('FRONTEND_BASE_URL', default='echodesk.ge')
REVALIDATION_SECRET = config('REVALIDATION_SECRET', default='your-secret-key-here')

# Optional: For advanced deployments
VERCEL_TOKEN = config('VERCEL_TOKEN', default='')
VERCEL_PROJECT_ID = config('VERCEL_PROJECT_ID', default='')

# Facebook Integration Settings
FACEBOOK_APP_ID = config('FACEBOOK_APP_ID', default='')
FACEBOOK_APP_SECRET = config('FACEBOOK_APP_SECRET', default='')
FACEBOOK_APP_VERSION = config('FACEBOOK_APP_VERSION', default='v23.0')

# Social Integration Configuration
SOCIAL_INTEGRATIONS = {
    'FACEBOOK_APP_ID': FACEBOOK_APP_ID,
    'FACEBOOK_APP_SECRET': FACEBOOK_APP_SECRET,
    'FACEBOOK_API_VERSION': FACEBOOK_APP_VERSION,
    'FACEBOOK_VERIFY_TOKEN': config('FACEBOOK_WEBHOOK_VERIFY_TOKEN', default='echodesk_webhook_token_2024'),
    'FACEBOOK_SCOPES': [
        'business_management',  # Essential for accessing Pages and Business assets
        'pages_messaging',  # Read and send messages on behalf of pages
        'pages_show_list',  # Access list of pages
        'pages_read_engagement',  # Read page posts and comments
        'pages_manage_metadata',  # Access page metadata
        'public_profile',  # Basic profile information
        'email',  # Email address
    ],
}

# ASGI Application for WebSocket support
ASGI_APPLICATION = 'amanati_crm.asgi.application'

# Channel Layers configuration for WebSocket support
# Password is included in the hosts tuple format if needed
redis_password = config('REDIS_PASSWORD', default=None)
redis_host = config('REDIS_HOST', default='127.0.0.1')
redis_port = config('REDIS_PORT', default=6379, cast=int)

if redis_password:
    # Format: rediss:// (with double 's' for SSL) for DigitalOcean managed Redis
    redis_url = f'rediss://:{redis_password}@{redis_host}:{redis_port}/0'
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [redis_url],
            },
        },
    }
else:
    # Local development without password
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                "hosts": [(redis_host, redis_port)],
            },
        },
    }

# Bank of Georgia (BOG) Payment Gateway Configuration
# Documentation: https://api.bog.ge/docs/en/payments/introduction
# Get credentials from BOG merchant portal
#
# TEST ENVIRONMENT (current default):
#   Auth: https://account-ob-test.bog.ge/auth/realms/bog-test/protocol/openid-connect/token
#   API: https://api-test.bog.ge/payments/v1
#
# PRODUCTION ENVIRONMENT:
#   Auth: https://oauth2.bog.ge/auth/realms/bog/protocol/openid-connect/token
#   API: https://api.bog.ge/payments/v1
# TEST ENVIRONMENT:
#   Auth: https://account-ob-test.bog.ge/auth/realms/bog-test/protocol/openid-connect/token
#   API: https://api-test.bog.ge/payments/v1

# BOG Payment Gateway Configuration
# All credentials must be provided via environment variables
BOG_CLIENT_ID = config('BOG_CLIENT_ID', default='')
BOG_CLIENT_SECRET = config('BOG_CLIENT_SECRET', default='')
BOG_AUTH_URL = config('BOG_AUTH_URL', default='https://oauth2.bog.ge/auth/realms/bog/protocol/openid-connect/token')
BOG_API_BASE_URL = config('BOG_API_BASE_URL', default='https://api.bog.ge/payments/v1')

# Cron Job Security Token (for scheduled task HTTP endpoints)
CRON_SECRET_TOKEN = config('CRON_SECRET_TOKEN', default='')

# Test Mode for Billing Intervals
# When True, subscriptions renew every 2 minutes instead of 30 days (for testing)
# Set TEST_BILLING_INTERVAL=true in .env to enable test mode
TEST_BILLING_INTERVAL = config('TEST_BILLING_INTERVAL', default=False, cast=bool)

# SendGrid Email Configuration
SENDGRID_API_KEY = config('SENDGRID_API_KEY', default='')
SENDGRID_FROM_EMAIL = config('SENDGRID_FROM_EMAIL', default='noreply@email.echodesk.ge')
SENDGRID_FROM_NAME = config('SENDGRID_FROM_NAME', default='EchoDesk')

# Email Backend Configuration
# Use SendGrid SMTP or API for sending emails
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'  # This is always 'apikey' for SendGrid
EMAIL_HOST_PASSWORD = SENDGRID_API_KEY
DEFAULT_FROM_EMAIL = SENDGRID_FROM_EMAIL
SERVER_EMAIL = SENDGRID_FROM_EMAIL
