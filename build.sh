#!/bin/bash
# EchoDesk Multi-Tenant Build Script

set -e  # Exit on any error

echo "🚀 Building EchoDesk Multi-Tenant CRM"
echo "====================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found, copying from .env.example"
    cp .env.example .env
    print_warning "Please configure your .env file with proper database credentials"
fi

# Install/Update dependencies
print_status "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
print_success "Dependencies installed"

# Run system checks
print_status "Running Django system checks..."
python manage.py check
print_success "System checks passed"

# Check database connection
print_status "Testing database connection..."
if python manage.py shell -c "from django.db import connection; connection.cursor()" 2>/dev/null; then
    print_success "Database connection successful"
else
    print_error "Database connection failed. Please check your .env configuration"
    exit 1
fi

# Run migrations for shared schema
print_status "Running shared schema migrations..."
python manage.py migrate_schemas --shared
print_success "Shared schema migrations completed"

# Check if superuser exists
print_status "Checking for superuser..."
SUPERUSER_EXISTS=$(python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
from tenant_schemas.utils import schema_context, get_public_schema_name
with schema_context(get_public_schema_name()):
    print(User.objects.filter(is_superuser=True).exists())
" 2>/dev/null || echo "False")

if [ "$SUPERUSER_EXISTS" = "False" ]; then
    print_warning "No superuser found. You'll need to create one manually:"
    echo "python manage.py createsuperuser"
else
    print_success "Superuser exists"
fi

# Check for tenants
print_status "Checking existing tenants..."
TENANT_COUNT=$(python manage.py shell -c "
from tenants.models import Tenant
print(Tenant.objects.count())
" 2>/dev/null || echo "0")

print_success "Found $TENANT_COUNT tenants"

if [ "$TENANT_COUNT" = "0" ]; then
    print_warning "No tenants found. Create one with:"
    echo "python manage.py create_tenant demo 'Demo Company' demo.echodesk.ge admin@demo.com 'Demo Admin' --admin-password 'demo123'"
fi

# Run tenant migrations
if [ "$TENANT_COUNT" != "0" ]; then
    print_status "Running tenant migrations..."
    python manage.py migrate_schemas
    print_success "Tenant migrations completed"
fi

# Collect static files
print_status "Collecting static files..."
python manage.py collectstatic --noinput
print_success "Static files collected"

# Run tests if they exist
if [ -d "tests" ] || find . -name "test_*.py" -not -path "./venv/*" | grep -q .; then
    print_status "Running tests..."
    python manage.py test --verbosity=2
    print_success "Tests passed"
else
    print_warning "No tests found"
fi

echo ""
echo "🎉 Build completed successfully!"
echo "================================"
print_success "EchoDesk Multi-Tenant CRM is ready to run"
echo ""
echo "🚀 Start the development server:"
echo "   python manage.py runserver"
echo ""
echo "🌐 Access URLs:"
echo "   • Public Admin: http://localhost:8000/admin/"
echo "   • API Docs: http://localhost:8000/api/docs/"
echo ""
if [ "$TENANT_COUNT" != "0" ]; then
    echo "📋 Tenant URLs (add to /etc/hosts for local testing):"
    python manage.py shell -c "
from tenants.models import Tenant
for tenant in Tenant.objects.all():
    subdomain = tenant.domain_url.split('.')[0]
    print(f'   • {tenant.name}: http://{subdomain}.localhost:8000/')
    print(f'     Admin: {tenant.admin_email}')
"
fi
echo ""
echo "💡 Next steps:"
echo "   1. Configure your .env file with production database settings"
echo "   2. Create a superuser if needed: python manage.py createsuperuser"
echo "   3. Create tenants: python manage.py create_tenant ..."
echo "   4. Add tenant subdomains to /etc/hosts for local testing"
