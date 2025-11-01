# Tickets App Tests

Comprehensive test suite for the ticketing system (tickets app).

## Test Structure

```
tickets/tests/
├── __init__.py
├── test_utils.py         # Test data factories and helpers
├── test_models.py        # Model tests (60+ tests)
├── test_api.py           # API endpoint tests (40+ tests)
└── README.md            # This file
```

## Test Coverage

### Models Tested
- **Board** - Kanban board management
- **TicketColumn** - Board columns/statuses
- **Tag** - Ticket tags/labels
- **Ticket** - Main ticket model with payment tracking
- **SubTicket** - Hierarchical ticket relationships
- **ChecklistItem** - Ticket checklist items
- **TicketComment** - Ticket comments
- **TicketTimeLog** - Time tracking in columns
- **TicketPayment** - Payment tracking

### Features Tested
- Model creation and validation
- String representations
- Properties and methods
- Cascade deletions
- Uniqueness constraints
- Auto-increment positions
- Payment calculations
- Time tracking
- API CRUD operations
- Filtering and querying
- Authentication and permissions

## Running Tests

### Run all tickets tests
```bash
python manage.py test --settings=ecommerce_crm.tests.test_settings tickets.tests --verbosity=2
```

### Run specific test file
```bash
python manage.py test --settings=ecommerce_crm.tests.test_settings tickets.tests.test_models --verbosity=2
python manage.py test --settings=ecommerce_crm.tests.test_settings tickets.tests.test_api --verbosity=2
```

### Run specific test class
```bash
python manage.py test --settings=ecommerce_crm.tests.test_settings tickets.tests.test_models.TicketModelTest --verbosity=2
```

### Run specific test method
```bash
python manage.py test --settings=ecommerce_crm.tests.test_settings tickets.tests.test_models.TicketModelTest.test_ticket_payment_status_paid --verbosity=2
```

### Run with coverage
```bash
coverage run --source='tickets' manage.py test --settings=ecommerce_crm.tests.test_settings tickets.tests
coverage report
coverage html  # Generate HTML report
```

### Using Makefile shortcuts
```bash
make test-tickets         # Run all tickets tests
make test-tickets-models  # Run model tests only
make test-tickets-api     # Run API tests only
```

## Test Data Utilities

The `test_utils.py` file provides helper functions for creating test data:

```python
from tickets.tests.test_utils import TestDataMixin

class MyTest(TestCase, TestDataMixin):
    def test_something(self):
        # Create test user
        user = self.create_test_user()

        # Create test board
        board = self.create_test_board()

        # Create test column
        column = self.create_test_column(board=board)

        # Create test ticket
        ticket = self.create_test_ticket(column=column)
```

## Test Examples

### Model Tests
```python
def test_ticket_payment_status_paid(self):
    """Test payment status when fully paid."""
    ticket = self.create_test_ticket(
        price=Decimal('100.00'),
        amount_paid=Decimal('100.00'),
        is_paid=True
    )
    self.assertEqual(ticket.payment_status, 'paid')
```

### API Tests
```python
def test_create_ticket(self):
    """Test creating a ticket via API."""
    url = reverse('tickets:ticket-list')
    data = {
        'title': 'New Ticket',
        'description': 'Test description',
        'priority': 'high',
        'column': self.column.id
    }

    response = self.client.post(url, data)
    self.assertEqual(response.status_code, status.HTTP_201_CREATED)
```

## Adding New Tests

When adding new features to the tickets app:

1. Add model tests to `test_models.py`
2. Add API tests to `test_api.py`
3. Update test utilities in `test_utils.py` if needed
4. Run tests to ensure they pass
5. Update this README if needed

## Best Practices

1. **Use test utilities**: Leverage `TestDataMixin` for consistent test data
2. **Test edge cases**: Don't just test the happy path
3. **Test validation**: Ensure models validate data correctly
4. **Test permissions**: Verify API endpoints respect permissions
5. **Test relationships**: Check cascade deletes and foreign keys
6. **Keep tests isolated**: Each test should be independent
7. **Use descriptive names**: Test names should describe what they test

## CI/CD Integration

These tests are automatically run:
- On every push to main/develop branches
- On every pull request
- Before commits (if pre-commit hooks are installed)

See `.github/workflows/tests.yml` for CI configuration.

## Troubleshooting

### Tests fail with database errors
Make sure you're using the test settings:
```bash
python manage.py test --settings=ecommerce_crm.tests.test_settings tickets.tests
```

### Import errors
Ensure the tickets app is in INSTALLED_APPS in test_settings.py

### Permission errors
Check that test users have appropriate permissions for the actions being tested

## Test Statistics

- **Total Tests**: 100+
- **Models Tested**: 9
- **API Endpoints Tested**: 8+
- **Coverage Target**: >80%

Run `coverage report` to see current coverage statistics.
