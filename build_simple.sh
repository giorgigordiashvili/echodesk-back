#!/bin/bash
# Simple build script for EchoDesk Multi-Tenant CRM

echo "🚀 Building EchoDesk Multi-Tenant CRM..."

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Run system checks
echo "🔍 Running system checks..."
python manage.py check

# Test database connection
echo "🗄️ Testing database connection..."
python manage.py shell -c "from django.db import connection; connection.cursor(); print('Database connection OK')"

# Run shared migrations
echo "🔄 Running shared schema migrations..."
python manage.py migrate_schemas --shared

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Check tenants
echo "🏢 Checking tenants..."
python manage.py shell -c "
from tenants.models import Tenant
count = Tenant.objects.count()
print(f'Found {count} tenants')
if count > 0:
    for tenant in Tenant.objects.all():
        print(f'  - {tenant.name} ({tenant.domain_url})')
"

# Run tenant migrations if tenants exist
echo "🔄 Running tenant migrations..."
python manage.py migrate_schemas

echo "✅ Build completed successfully!"
echo ""
echo "🚀 To start the server:"
echo "   source venv/bin/activate"
echo "   python manage.py runserver"
echo ""
echo "🌐 Access URLs:"
echo "   • Public Admin: http://localhost:8000/admin/"
echo "   • API Docs: http://localhost:8000/api/docs/"
