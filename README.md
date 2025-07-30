# EchoDesk Backend

Django-based backend for the EchoDesk CRM system with multi-tenant architecture.

Updated: July 31, 2025 - Enhanced user management system with comprehensive role-based permissions and team management functionality.

## 🏗️ Architecture

- **Main Domain (`echodesk.ge`)**: Public schema for tenant management and main dashboard
- **Tenant Subdomains (`*.echodesk.ge`)**: Each tenant gets its own subdomain with isolated database schema
- **Automatic Routing**: Subdomain-based tenant detection with fallback to public schema

## ✨ Features

- **Multi-tenancy**: Each tenant has its own subdomain and isolated database schema
- **User Management**: Tenant-specific user authentication and authorization
- **CRM Functionality**: Call logs, client management
- **REST API**: Fully documented API with Swagger/OpenAPI
- **Admin Interface**: Django admin for tenant and user management
- **Wildcard Subdomain Support**: Automatic tenant routing via subdomains

## 🌐 Domain Structure

```
echodesk.ge                    → Public schema (tenant management)
├── admin/                     → Main admin dashboard
├── api/docs/                  → API documentation
└── api/tenants/              → Tenant management API

demo.echodesk.ge              → Demo tenant schema
├── admin/                    → Tenant admin
├── api/users/                → Tenant users API
└── api/call-logs/            → Tenant CRM API

acme.echodesk.ge              → Acme tenant schema
├── admin/                    → Tenant admin
├── api/users/                → Tenant users API
└── api/call-logs/            → Tenant CRM API
```

## 🚀 Tech Stack

- Django 4.2+ with Django REST Framework
- PostgreSQL (required for schema-based multi-tenancy)
- django-tenant-schemas for multi-tenancy
- drf-spectacular for API documentation
- Custom middleware for domain routing

## 📋 Setup Instructions

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Virtual environment (recommended)

### 1. Clone and Setup Environment

```bash
git clone https://github.com/giorgigordiashvili/echodesk-back.git
cd echodesk-back
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the example environment file and configure it:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
SECRET_KEY=your-very-secret-key-here
DEBUG=True
MAIN_DOMAIN=echodesk.ge
DB_NAME=echodesk_db
DB_USER=echodesk_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### 3. Build and Setup

Run the automated build script:

```bash
chmod +x build.sh
./build.sh
```

Or manually:

```bash
# Run shared schema migrations
python manage.py migrate_schemas --shared

# Create superuser for public schema
python manage.py createsuperuser

# Create your first tenant
python manage.py create_tenant demo "Demo Company" demo.echodesk.ge admin@demo.com "Demo Admin" --admin-password "demo123"

# Run tenant migrations
python manage.py migrate_schemas

# Start development server
python manage.py runserver
```

## 🌐 Access URLs

### Production (DigitalOcean)
- **Main Dashboard**: https://echodesk.ge/admin/
- **API Docs**: https://echodesk.ge/api/docs/
- **Demo Tenant**: https://demo.echodesk.ge/admin/
- **Acme Tenant**: https://acme.echodesk.ge/admin/

### Local Development
- **Main Dashboard**: http://localhost:8000/admin/
- **API Docs**: http://localhost:8000/api/docs/
- **Demo Tenant**: http://demo.localhost:8000/admin/
- **Acme Tenant**: http://acme.localhost:8000/admin/

### For Local Development

Add entries to your `/etc/hosts` file:

```bash
127.0.0.1 localhost
127.0.0.1 demo.localhost
127.0.0.1 acme.localhost
```

## 🔧 Management Commands

### Create a New Tenant

```bash
python manage.py create_tenant <schema_name> <name> <domain> <admin_email> <admin_name> [--admin-password <password>]
```

Example:
```bash
python manage.py create_tenant startup "Startup Inc" startup.echodesk.ge admin@startup.com "Jane Smith" --admin-password "startup123"
```

### List All Tenants

```bash
python manage.py shell -c "
from tenants.models import Tenant
for tenant in Tenant.objects.all():
    print(f'{tenant.name}: {tenant.domain_url}')
"
```

## 📡 API Endpoints

### Public Schema (Main Domain)
- `GET /api/tenants/` - List all tenants
- `POST /api/tenants/` - Create new tenant
- `GET /api/tenants/{id}/users/` - List tenant users
- `POST /api/tenants/{id}/create_admin_user/` - Create admin user for tenant

### Tenant Schema (Per Subdomain)
- `GET /api/users/` - List users in current tenant
- `GET /api/call-logs/` - List call logs
- `POST /api/call-logs/` - Create call log
- `GET /api/clients/` - List clients
- `POST /api/clients/` - Create client

## 🚀 Deployment on DigitalOcean

The project is configured for automatic deployment on DigitalOcean App Platform.

### DNS Configuration

Set up your DNS with the following records:

```
A     echodesk.ge          → [Your DigitalOcean App IP]
CNAME *.echodesk.ge        → echodesk.ge
```

### Environment Variables

In DigitalOcean App Platform, set these environment variables:

```
SECRET_KEY=your-production-secret-key
DEBUG=False
MAIN_DOMAIN=echodesk.ge
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=your_database_host
DB_PORT=your_database_port
```

### Automatic Deployment

1. Push to the `main` branch
2. DigitalOcean App Platform will automatically build and deploy
3. The build script handles migrations and setup

## 🏗️ Project Structure

```
├── amanati_crm/              # Main Django project
│   ├── settings.py           # Multi-tenant Django settings
│   ├── urls.py              # Tenant-specific URLs
│   ├── urls_public.py       # Public schema URLs
│   └── middleware.py        # Custom tenant routing middleware
├── tenants/                 # Tenant management app
│   ├── models.py            # Tenant model
│   ├── views.py             # Tenant management API
│   └── management/          # Management commands
├── users/                   # User management app
│   ├── models.py            # Custom User model
│   └── views.py             # User management API
├── crm/                     # CRM functionality
│   ├── models.py            # CallLog, Client models
│   ├── serializers.py       # API serializers
│   └── views.py             # CRM API endpoints
├── build.sh                 # Local build script
├── build_production.sh      # Production build script
└── .do/app.yaml            # DigitalOcean configuration
```

## 🔧 Development

### Adding New Tenant-Specific Features

1. Add models to apps in `TENANT_APPS`
2. Create migrations: `python manage.py makemigrations`
3. Apply to all tenants: `python manage.py migrate_schemas`

### Adding Public Features

1. Add models to apps in `SHARED_APPS`
2. Create migrations: `python manage.py makemigrations`
3. Apply to public schema: `python manage.py migrate_schemas --shared`

## 🐛 Troubleshooting

### Common Issues

1. **"Tenant not found"**: Check subdomain spelling and DNS configuration
2. **"relation does not exist"**: Run migrations for the correct schema
3. **CORS errors**: Verify domain configuration in settings

### Useful Commands

```bash
# Check system status
python manage.py check

# Test tenant setup
python test_tenants.py

# Access Django shell in tenant context
python manage.py tenant_command shell --schema=demo
```

## 📚 API Documentation

Visit `/api/docs/` on any domain for interactive Swagger documentation.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

[Add your license information here]
