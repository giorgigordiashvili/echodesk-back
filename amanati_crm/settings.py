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
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

# Tenant model
TENANT_MODEL = "tenants.Tenant"

MIDDLEWARE = [
    'amanati_crm.middleware.EchoDeskTenantMiddleware',  # Custom tenant middleware (must be first)
    'tenants.subscription_middleware.SubscriptionMiddleware',  # Subscription feature middleware
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

# Spectacular settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'EchoDesk API',
    'DESCRIPTION': 'Multi-tenant CRM system for EchoDesk',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
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
# Removed ASGI and WebSocket support for simplicity
# Using simple polling instead of real-time WebSocket connections
