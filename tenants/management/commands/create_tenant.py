from django.core.management.base import BaseCommand
from tenant_schemas.utils import get_public_schema_name, schema_context
from tenants.models import Tenant
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Create a new tenant with optional admin user'
    
    def add_arguments(self, parser):
        parser.add_argument('schema_name', type=str, help='Schema name for the tenant')
        parser.add_argument('name', type=str, help='Display name for the tenant')
        parser.add_argument('domain', type=str, help='Domain name (e.g., acme.echodesk.ge)')
        parser.add_argument('admin_email', type=str, help='Admin email for the tenant')
        parser.add_argument('admin_name', type=str, help='Admin name for the tenant')
        parser.add_argument('--plan', type=str, default='basic', help='Subscription plan')
        parser.add_argument('--admin-password', type=str, help='Admin user password (if provided, creates admin user)')
    
    def handle(self, *args, **options):
        # Ensure we're in the public schema
        with schema_context(get_public_schema_name()):
            # Check if tenant already exists
            if Tenant.objects.filter(schema_name=options['schema_name']).exists():
                self.stdout.write(
                    self.style.ERROR(f'Tenant with schema "{options["schema_name"]}" already exists')
                )
                return
            
            # Check if domain already exists
            if Tenant.objects.filter(domain_url=options['domain']).exists():
                self.stdout.write(
                    self.style.ERROR(f'Domain "{options["domain"]}" already exists')
                )
                return
            
            # Create tenant
            tenant = Tenant.objects.create(
                schema_name=options['schema_name'],
                domain_url=options['domain'],
                name=options['name'],
                admin_email=options['admin_email'],
                admin_name=options['admin_name'],
                plan=options['plan']
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created tenant "{tenant.name}" with domain "{tenant.domain_url}"'
                )
            )
            
            # Create admin user if password provided
            if options.get('admin_password'):
                with schema_context(tenant.schema_name):
                    name_parts = options['admin_name'].split()
                    first_name = name_parts[0] if name_parts else ''
                    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
                    
                    admin_user = User.objects.create_superuser(
                        email=options['admin_email'],
                        password=options['admin_password'],
                        first_name=first_name,
                        last_name=last_name
                    )
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'Successfully created admin user: {admin_user.email}')
                    )
