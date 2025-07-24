#!/bin/bash
# Production build script for DigitalOcean App Platform
# Multi-tenant Django application

set -e  # Exit on any error

echo "🚀 Building EchoDesk Multi-Tenant CRM for Production"
echo "=================================================="

# Install dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run system checks
echo "🔍 Running system checks..."
python manage.py check --deploy

# Collect static files
echo "📁 Collecting static files..."
python manage.py collectstatic --noinput

# Run migrations for shared schema
echo "🗄️ Running shared schema migrations..."
python manage.py migrate_schemas --shared

echo "✅ Production build completed successfully!"
echo ""
echo "🌐 Multi-tenant setup ready for:"
echo "   • Main domain: echodesk.ge"
echo "   • Tenant subdomains: *.echodesk.ge"
echo "   • API Documentation: /api/docs/"
echo ""
echo "🔧 Post-deployment tasks:"
echo "   1. Create superuser: python manage.py createsuperuser"
echo "   2. Create tenants: python manage.py create_tenant ..."
echo "   3. Configure DNS wildcard: *.echodesk.ge"
