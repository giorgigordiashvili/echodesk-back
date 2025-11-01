# Ecommerce CRM Tests

## Running Tests

### Run all ecommerce tests:
```bash
python manage.py test ecommerce_crm.tests
```

### Run specific test file:
```bash
python manage.py test ecommerce_crm.tests.test_models
python manage.py test ecommerce_crm.tests.test_authentication
python manage.py test ecommerce_crm.tests.test_password_reset
python manage.py test ecommerce_crm.tests.test_email
python manage.py test ecommerce_crm.tests.test_api
python manage.py test ecommerce_crm.tests.test_serializers
```

### Run specific test class:
```bash
python manage.py test ecommerce_crm.tests.test_models.ProductModelTest
python manage.py test ecommerce_crm.tests.test_authentication.ClientLoginTest
```

### Run specific test method:
```bash
python manage.py test ecommerce_crm.tests.test_models.ProductModelTest.test_create_product
```

### Run with verbosity:
```bash
python manage.py test ecommerce_crm.tests --verbosity=2
```

### Keep test database (for debugging):
```bash
python manage.py test ecommerce_crm.tests --keepdb
```

### Run in parallel:
```bash
python manage.py test ecommerce_crm.tests --parallel
```

## Test Coverage

### Install coverage:
```bash
pip install coverage
```

### Run tests with coverage:
```bash
coverage run --source='ecommerce_crm' manage.py test ecommerce_crm.tests
```

### View coverage report:
```bash
coverage report
```

### Generate HTML coverage report:
```bash
coverage html
# Open htmlcov/index.html in browser
```

## Test Organization

- `test_utils.py` - Test utilities and helper functions
- `test_models.py` - Model tests (Language, Product, Client, Order, etc.)
- `test_authentication.py` - Registration, login, JWT token tests
- `test_password_reset.py` - Password reset flow tests
- `test_email.py` - Email sending tests (welcome, password reset)
- `test_api.py` - API endpoint tests (Product, Cart, Orders, etc.)
- `test_serializers.py` - Serializer validation tests

## Note on Multi-tenant Testing

This app uses django-tenant-schemas for multi-tenancy. For unit tests that don't require full tenant context, we use standard `TestCase` and `APITestCase`.

For tests that specifically need tenant schemas, use:
```python
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient
```

## Database Configuration

Tests use an in-memory SQLite database by default for speed and simplicity. The production PostgreSQL database is not used for testing to avoid data conflicts and connection issues.

Email tests use Django's `locmem` backend which stores emails in memory for verification.
