from django.core.management.base import BaseCommand
from tenant_schemas.utils import schema_context
from django.contrib.auth import get_user_model
from tenants.models import Tenant

User = get_user_model()


class Command(BaseCommand):
    help = 'Create admin user for a tenant'
    
    def add_arguments(self, parser):
        parser.add_argument('schema_name', type=str, help='Schema name of the tenant')
        parser.add_argument('email', type=str, help='Admin email')
        parser.add_argument('password', type=str, help='Admin password')
        parser.add_argument('--first-name', type=str, default='', help='First name')
        parser.add_argument('--last-name', type=str, default='', help='Last name')
    
    def handle(self, *args, **options):
        try:
            tenant = Tenant.objects.get(schema_name=options['schema_name'])
        except Tenant.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Tenant with schema "{options["schema_name"]}" does not exist')
            )
            return
        
        with schema_context(tenant.schema_name):
            if User.objects.filter(email=options['email']).exists():
                self.stdout.write(
                    self.style.ERROR(f'User with email "{options["email"]}" already exists in this tenant')
                )
                return
            
            user = User.objects.create_user(
                email=options['email'],
                password=options['password'],
                first_name=options['first_name'],
                last_name=options['last_name'],
                is_staff=True,
                is_superuser=True
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully created admin user "{user.email}" for tenant "{tenant.name}"'
                )
            )
