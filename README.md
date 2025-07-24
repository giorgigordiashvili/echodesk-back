# Amanati CRM API

A clean Django 4.2+ REST API project with JWT authentication and PostgreSQL database.

## Features

- Custom User model with email as username
- JWT authentication using djangorestframework-simplejwt
- User registration, login, and profile endpoints
- PostgreSQL database with SSL support
- Django REST Framework
- **Enhanced Admin Dashboard** with statistics and user management
- Production-ready configuration for DigitalOcean deployment

## API Endpoints

### Authentication APIs
- `POST /api/register/` - Register new user (email, password)
- `POST /api/login/` - Obtain access/refresh JWT tokens
- `POST /api/token/refresh/` - Refresh access token
- `GET /api/profile/` - Get authenticated user's profile data

### Admin Dashboard
- `/admin/` - Enhanced admin dashboard with user statistics
- Root URL `/` redirects to admin dashboard

## Setup Instructions (Local Development)

1. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env file with your database credentials
   ```

4. **Run migrations:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

5. **Create superuser (optional):**
   ```bash
   python manage.py createsuperuser
   ```

6. **Run development server:**
   ```bash
   python manage.py runserver
   ```

## Database Configuration

The project is configured to use PostgreSQL with SSL support. Configure your database credentials in the `.env` file:

- **Engine**: PostgreSQL
- **SSL**: Required (for production databases)
- **Configuration**: Set via environment variables

All database credentials are managed through environment variables for security. Copy `.env.example` to `.env` and update with your actual database credentials.

## API Usage Examples

### Register User
```bash
curl -X POST http://localhost:8000/api/register/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123",
    "password_confirm": "securepassword123",
    "first_name": "John",
    "last_name": "Doe"
  }'
```

### Login
```bash
curl -X POST http://localhost:8000/api/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepassword123"
  }'
```

### Get Profile (requires authentication)
```bash
curl -X GET http://localhost:8000/api/profile/ \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Refresh Token
```bash
curl -X POST http://localhost:8000/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{
    "refresh": "YOUR_REFRESH_TOKEN"
  }'
```

## DigitalOcean App Platform Deployment

App Platform is the easiest way to deploy this Django application with automatic scaling, SSL certificates, and continuous deployment from GitHub.

### Step 1: Create App on DigitalOcean

1. Go to [DigitalOcean App Platform](https://cloud.digitalocean.com/apps)
2. Click "Create App"
3. Choose "GitHub" as source
4. Select your repository: `giorgigordiashvili/echodesk-back`
5. Choose branch: `main`
6. App Platform will auto-detect it's a Python app

### Step 2: Configure Build Settings

App Platform should automatically detect the configuration from `.do/app.yaml`, but verify:

- **Build Command**: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
- **Run Command**: `gunicorn amanati_crm.wsgi:application --bind 0.0.0.0:8000`
- **HTTP Port**: `8000`

### Step 3: Set Environment Variables

In the App Platform dashboard, add these environment variables:

```
DEBUG=False
SECRET_KEY=your-production-secret-key-here
ALLOWED_HOSTS=your-app-domain.ondigitalocean.app,api.echodesk.ge
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=your_database_host
DB_PORT=your_database_port

# Admin user configuration (optional)
ADMIN_EMAIL=your-admin@email.com
ADMIN_PASSWORD=your-secure-admin-password
```

### Step 4: Deploy

1. Click "Create Resources"
2. App Platform will build and deploy your app
3. You'll get a URL like `https://your-app-name.ondigitalocean.app`

### Step 5: Custom Domain (Optional)

1. In App Platform dashboard, go to "Settings" → "Domains"
2. Add your custom domain: `api.echodesk.ge`
3. Update your domain's DNS to point to the provided CNAME
4. SSL certificate will be automatically provisioned

### Automatic Deployments

Every time you push to the `main` branch, App Platform will automatically rebuild and deploy your application.

### Monitoring and Logs

- View application logs in the App Platform dashboard
- Monitor performance and scaling
- Set up alerts for issues

## API Usage Examples

1. Go to [DigitalOcean App Platform](https://cloud.digitalocean.com/apps)
2. Click "Create App"
3. Choose "GitHub" as source
4. Select your repository: `giorgigordiashvili/echodesk-back`
5. Choose branch: `main`

### Step 2: Configure Your App

1. **App Name**: `echodesk-api`
2. **Region**: Choose closest to your users
3. **Plan**: Basic ($5/month) or Professional ($12/month)

### Step 3: Set Environment Variables

In the App Platform dashboard, go to Settings > Environment Variables and add:

```
DEBUG=False
SECRET_KEY=your-generated-secret-key-here
ALLOWED_HOSTS=your-app-domain.ondigitalocean.app,api.echodesk.ge

# Database Configuration
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DB_HOST=your_database_host
DB_PORT=your_database_port
```

**🔒 Important**: Never commit these real values to GitHub. Set them only in the App Platform dashboard.

### Step 4: Domain Configuration

1. In App Platform, go to Settings > Domains
2. Add your custom domain: `api.echodesk.ge`
3. Update your DNS to point to the provided CNAME
4. SSL certificate will be automatically provisioned

### Step 5: Deploy

1. App Platform will automatically deploy when you push to main branch
2. You can also manually trigger deployments from the dashboard
3. Monitor logs in the Runtime Logs section

### API Endpoints

After deployment, your API will be available at:
- `https://your-app-name.ondigitalocean.app/api/register/`
- `https://your-app-name.ondigitalocean.app/api/login/`
- `https://your-app-name.ondigitalocean.app/api/token/refresh/`
- `https://your-app-name.ondigitalocean.app/api/profile/`

Or with your custom domain:
- `https://api.echodesk.ge/api/register/`
- `https://api.echodesk.ge/api/login/`
- `https://api.echodesk.ge/api/token/refresh/`
- `https://api.echodesk.ge/api/profile/`

## Admin Dashboard Features

### Dashboard Overview
- **User Statistics**: Total, active, inactive, and staff user counts
- **Recent Users**: Latest registered users with status indicators
- **Quick Actions**: Direct links to common admin tasks
- **Visual Indicators**: Color-coded status badges and progress indicators

### User Management
- **Enhanced User List**: Comprehensive user information display
- **Advanced Filtering**: Filter by status, role, registration date
- **Bulk Actions**: Activate/deactivate multiple users at once
- **User Details**: Full user profile with permissions management
- **Search Functionality**: Find users by email, name, or other criteria

### Admin Features
- **Custom Dashboard**: Beautiful overview with statistics
- **Responsive Design**: Works on desktop and mobile devices
- **User Status Badges**: Visual indicators for user states
- **Quick Navigation**: Easy access to all admin functions
- **Bulk Operations**: Manage multiple users efficiently

### Default Admin Credentials
- **Email**: `admin@amanati.com`
- **Password**: `admin123`

**🔒 Important**: Change the default admin password immediately after first login!

## Project Structure

```
amanati_crm/
├── manage.py
├── requirements.txt
├── build.sh                    # Build script for App Platform
├── .do/
│   └── app.yaml               # App Platform configuration
├── amanati_crm/
│   ├── __init__.py
│   ├── settings.py            # Django settings with PostgreSQL
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
└── users/
    ├── __init__.py
    ├── admin.py
    ├── apps.py
    ├── models.py              # Custom User model
    ├── serializers.py         # DRF serializers
    ├── views.py               # API views
    ├── urls.py                # API endpoints
    ├── tests.py
    └── migrations/
        ├── __init__.py
        └── 0001_initial.py    # User model migration
```

## Technologies Used

- **Backend**: Django 4.2+ with Django REST Framework
- **Database**: PostgreSQL with SSL (DigitalOcean Managed Database)
- **Authentication**: JWT tokens with djangorestframework-simplejwt
- **Deployment**: DigitalOcean App Platform
- **Static Files**: WhiteNoise for production static file serving
