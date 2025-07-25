from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from tenant_schemas.utils import get_public_schema_name, schema_context
from tenants.models import Tenant
from tickets.models import TicketColumn

User = get_user_model()


class Command(BaseCommand):
    help = 'Create default ticket columns for all tenants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=str,
            help='Create columns for specific tenant only (schema name)',
        )

    def handle(self, *args, **options):
        specific_tenant = options.get('tenant')
        
        if specific_tenant:
            # Create for specific tenant
            try:
                tenant = Tenant.objects.get(schema_name=specific_tenant)
                self.create_columns_for_tenant(tenant)
            except Tenant.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Tenant with schema "{specific_tenant}" not found')
                )
                return
        else:
            # Create for all tenants
            tenants = Tenant.objects.exclude(schema_name=get_public_schema_name())
            for tenant in tenants:
                self.create_columns_for_tenant(tenant)

    def create_columns_for_tenant(self, tenant):
        """Create default columns for a specific tenant."""
        with schema_context(tenant.schema_name):
            # Check if columns already exist
            if TicketColumn.objects.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f'Columns already exist for tenant "{tenant.name}" ({tenant.schema_name})'
                    )
                )
                return

            # Get a staff user to assign as creator (preferably superuser)
            creator = User.objects.filter(is_superuser=True).first()
            if not creator:
                creator = User.objects.filter(is_staff=True).first()
            
            if not creator:
                self.stdout.write(
                    self.style.ERROR(
                        f'No staff user found for tenant "{tenant.name}" ({tenant.schema_name}). '
                        'Cannot create columns.'
                    )
                )
                return

            # Default columns to create
            default_columns = [
                {
                    'name': 'To Do',
                    'description': 'New tickets that need to be started',
                    'color': '#EF4444',  # Red
                    'position': 1,
                    'is_default': True,
                    'is_closed_status': False,
                },
                {
                    'name': 'In Progress',
                    'description': 'Tickets currently being worked on',
                    'color': '#F59E0B',  # Amber
                    'position': 2,
                    'is_default': False,
                    'is_closed_status': False,
                },
                {
                    'name': 'Review',
                    'description': 'Tickets awaiting review or approval',
                    'color': '#3B82F6',  # Blue
                    'position': 3,
                    'is_default': False,
                    'is_closed_status': False,
                },
                {
                    'name': 'Done',
                    'description': 'Completed tickets',
                    'color': '#10B981',  # Green
                    'position': 4,
                    'is_default': False,
                    'is_closed_status': True,
                },
            ]

            created_columns = []
            for column_data in default_columns:
                column = TicketColumn.objects.create(
                    created_by=creator,
                    **column_data
                )
                created_columns.append(column)

            self.stdout.write(
                self.style.SUCCESS(
                    f'Created {len(created_columns)} default columns for tenant '
                    f'"{tenant.name}" ({tenant.schema_name})'
                )
            )

            # List created columns
            for column in created_columns:
                self.stdout.write(f'  - {column.name} ({column.color})')
