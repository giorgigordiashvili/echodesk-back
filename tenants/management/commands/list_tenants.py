from django.core.management.base import BaseCommand
from tenant_schemas.utils import get_public_schema_name, schema_context
from tenants.models import Tenant


class Command(BaseCommand):
    help = 'List all tenants'
    
    def handle(self, *args, **options):
        with schema_context(get_public_schema_name()):
            tenants = Tenant.objects.all()
            
            if not tenants.exists():
                self.stdout.write(self.style.WARNING('No tenants found'))
                return
            
            self.stdout.write(self.style.SUCCESS(f'Found {tenants.count()} tenant(s):'))
            self.stdout.write('')
            
            for tenant in tenants:
                self.stdout.write(f'Tenant: {tenant.name}')
                self.stdout.write(f'  Schema: {tenant.schema_name}')
                self.stdout.write(f'  Domain: {tenant.domain_url}')
                self.stdout.write(f'  Admin: {tenant.admin_name} ({tenant.admin_email})')
                self.stdout.write(f'  Plan: {tenant.plan}')
                self.stdout.write(f'  Active: {tenant.is_active}')
                self.stdout.write(f'  Created: {tenant.created_on}')
                self.stdout.write('')
