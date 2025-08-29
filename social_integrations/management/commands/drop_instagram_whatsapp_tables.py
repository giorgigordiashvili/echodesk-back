from django.core.management.base import BaseCommand
from django.db import connection
from tenant_schemas.utils import get_tenant_model, tenant_context

class Command(BaseCommand):
    help = 'Drop Instagram and WhatsApp tables from all tenant schemas'

    def handle(self, *args, **options):
        # Get all tenants
        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.exclude(schema_name='public')
        
        # Tables to drop
        tables_to_drop = [
            'social_integrations_instagramaccountconnection',
            'social_integrations_instagrammessage', 
            'social_integrations_whatsappbusinessconnection',
            'social_integrations_whatsappmessage'
        ]
        
        # Drop from public schema first
        self.stdout.write("Dropping Instagram and WhatsApp tables from public schema...")
        self.drop_schema_tables('public', tables_to_drop)
        
        # Drop from each tenant schema
        for tenant in tenants:
            self.stdout.write(f"Dropping Instagram and WhatsApp tables from tenant: {tenant.schema_name}")
            self.drop_schema_tables(tenant.schema_name, tables_to_drop)
            
        self.stdout.write(
            self.style.SUCCESS('Successfully dropped Instagram and WhatsApp tables from all schemas')
        )

    def drop_schema_tables(self, schema_name, tables):
        if schema_name != 'public':
            TenantModel = get_tenant_model()
            try:
                tenant = TenantModel.objects.get(schema_name=schema_name)
                with tenant_context(tenant):
                    self._drop_tables(schema_name, tables)
            except TenantModel.DoesNotExist:
                self.stdout.write(f"Tenant {schema_name} not found, skipping...")
                return
        else:
            self._drop_tables(schema_name, tables)

    def _drop_tables(self, schema_name, tables):
        with connection.cursor() as cursor:
            for table in tables:
                try:
                    # Check if table exists
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = %s 
                            AND table_name = %s
                        );
                    """, [schema_name, table])
                    
                    table_exists = cursor.fetchone()[0]
                    
                    if table_exists:
                        # Drop the table
                        if schema_name == 'public':
                            cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
                        else:
                            cursor.execute(f'DROP TABLE IF EXISTS "{schema_name}"."{table}" CASCADE;')
                        self.stdout.write(f"✅ Dropped table {table} from {schema_name}")
                    else:
                        self.stdout.write(f"ℹ️ Table {table} does not exist in {schema_name}")
                        
                except Exception as e:
                    self.stdout.write(f"❌ Error dropping {table} from {schema_name}: {e}")