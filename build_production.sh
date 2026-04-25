#!/bin/bash
# Production build script for DigitalOcean App Platform
# Multi-tenant Django application

set -e  # Exit on any error

echo "🚀 Building EchoDesk Multi-Tenant CRM for Production"
echo "=================================================="

# Install dependencies. We deliberately skip `pip install --upgrade pip` —
# the buildpack ships a recent pip already and the upgrade step adds ~10s
# to every deploy for no real benefit.
echo "📦 Installing dependencies..."
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

# Asterisk realtime migrations are intentionally NOT run here.
# Under Phase 2 (BYO Asterisk), each tenant owns their own asterisk DB and
# there's no single global alias to migrate. Run on demand:
#   python manage.py migrate_asterisk --database asterisk_<tenant>
#   python manage.py migrate_asterisk --all

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
