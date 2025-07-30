from django.core.management.base import BaseCommand
from django.db import connection
from tenants.models import Tenant


class Command(BaseCommand):
    help = 'Drop all tenants except amanati from the database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm that you want to delete all tenants except amanati',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            self.stdout.write(
                self.style.WARNING(
                    'This command will delete all tenants except "amanati" and their data.\n'
                    'Run with --confirm to proceed.'
                )
            )
            return

        # Get all tenants except amanati
        tenants_to_delete = Tenant.objects.exclude(schema_name__in=['public', 'amanati'])
        
        if not tenants_to_delete.exists():
            self.stdout.write(
                self.style.SUCCESS('No tenants to delete (only amanati exists)')
            )
            return

        self.stdout.write(f'Found {tenants_to_delete.count()} tenants to delete:')
        for tenant in tenants_to_delete:
            self.stdout.write(f'  - {tenant.schema_name} ({tenant.domain_url})')

        # Delete each tenant
        for tenant in tenants_to_delete:
            self.stdout.write(f'Deleting tenant: {tenant.schema_name}')
            
            # Drop the schema
            with connection.cursor() as cursor:
                cursor.execute(f'DROP SCHEMA IF EXISTS "{tenant.schema_name}" CASCADE')
            
            # Delete the tenant record
            tenant.delete()
            
            self.stdout.write(
                self.style.SUCCESS(f'Successfully deleted tenant: {tenant.schema_name}')
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully cleaned up {tenants_to_delete.count()} tenants. '
                'Only "amanati" tenant remains.'
            )
        )
