from django.core.management.base import BaseCommand
from django.db import connection
from tenant_schemas.utils import get_tenant_model, tenant_context

class Command(BaseCommand):
    help = 'Fix account_type constraint in InstagramAccountConnection table'

    def handle(self, *args, **options):
        # Get all tenants
        TenantModel = get_tenant_model()
        tenants = TenantModel.objects.exclude(schema_name='public')
        
        # Fix public schema first
        self.stdout.write("Fixing account_type constraint for public schema...")
        self.fix_schema_constraint('public')
        
        # Fix each tenant schema
        for tenant in tenants:
            self.stdout.write(f"Fixing account_type constraint for tenant: {tenant.schema_name}")
            self.fix_schema_constraint(tenant.schema_name)
            
        self.stdout.write(
            self.style.SUCCESS('Successfully fixed account_type constraint for all schemas')
        )

    def fix_schema_constraint(self, schema_name):
        if schema_name != 'public':
            TenantModel = get_tenant_model()
            try:
                tenant = TenantModel.objects.get(schema_name=schema_name)
                with tenant_context(tenant):
                    self._execute_fixes(schema_name)
            except TenantModel.DoesNotExist:
                self.stdout.write(f"Tenant {schema_name} not found, skipping...")
                return
        else:
            self._execute_fixes(schema_name)

    def _execute_fixes(self, schema_name):
        with connection.cursor() as cursor:
            try:
                # Check if the column exists and has NOT NULL constraint
                cursor.execute("""
                    SELECT column_name, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'social_integrations_instagramaccountconnection' 
                    AND column_name = 'account_type'
                    AND table_schema = %s;
                """, [schema_name])
                
                result = cursor.fetchone()
                if not result:
                    self.stdout.write(f"❌ account_type column not found in {schema_name}")
                    return
                    
                column_name, is_nullable = result
                
                if is_nullable == 'NO':
                    # Remove NOT NULL constraint
                    cursor.execute("""
                        ALTER TABLE social_integrations_instagramaccountconnection 
                        ALTER COLUMN account_type DROP NOT NULL;
                    """)
                    self.stdout.write(f"✅ Removed NOT NULL constraint for {schema_name}")
                else:
                    self.stdout.write(f"ℹ️ Column already nullable in {schema_name}")
                
                # Update existing NULL values to 'BUSINESS'
                cursor.execute("""
                    UPDATE social_integrations_instagramaccountconnection 
                    SET account_type = 'BUSINESS' 
                    WHERE account_type IS NULL;
                """)
                
                rows_updated = cursor.rowcount
                if rows_updated > 0:
                    self.stdout.write(f"✅ Updated {rows_updated} NULL values to 'BUSINESS' in {schema_name}")
                else:
                    self.stdout.write(f"ℹ️ No NULL values found in {schema_name}")
                    
            except Exception as e:
                self.stdout.write(f"❌ Error fixing {schema_name}: {e}")