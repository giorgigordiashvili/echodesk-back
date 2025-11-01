.PHONY: test test-fast test-coverage lint format clean help

help:
	@echo "Available commands:"
	@echo "  make test          - Run all tests"
	@echo "  make test-fast     - Run tests in parallel"
	@echo "  make test-coverage - Run tests with coverage report"
	@echo "  make lint          - Run code quality checks"
	@echo "  make format        - Auto-format code"
	@echo "  make clean         - Remove test artifacts"
	@echo "  make install-dev   - Install development dependencies"

install-dev:
	pip install -r requirements-dev.txt

test:
	python manage.py test --settings=ecommerce_crm.tests.test_settings ecommerce_crm.tests --verbosity=2

test-fast:
	python manage.py test --settings=ecommerce_crm.tests.test_settings ecommerce_crm.tests --parallel --verbosity=2

test-coverage:
	coverage run --source='ecommerce_crm' manage.py test --settings=ecommerce_crm.tests.test_settings ecommerce_crm.tests
	coverage report
	coverage html
	@echo "Coverage report generated in htmlcov/index.html"

test-models:
	python manage.py test --settings=ecommerce_crm.tests.test_settings ecommerce_crm.tests.test_models --verbosity=2

test-auth:
	python manage.py test --settings=ecommerce_crm.tests.test_settings ecommerce_crm.tests.test_authentication --verbosity=2

test-api:
	python manage.py test --settings=ecommerce_crm.tests.test_settings ecommerce_crm.tests.test_api --verbosity=2

lint:
	flake8 ecommerce_crm --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 ecommerce_crm --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

format:
	black ecommerce_crm
	isort ecommerce_crm

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	find . -type f -name '*.pyo' -delete
	find . -type f -name '.coverage' -delete
	rm -rf htmlcov
	rm -rf .pytest_cache
	rm -rf coverage.xml
	@echo "Cleaned test artifacts"

migrate:
	python manage.py migrate_schemas

migrations:
	python manage.py makemigrations

shell:
	python manage.py shell

run:
	python manage.py runserver

.DEFAULT_GOAL := help
