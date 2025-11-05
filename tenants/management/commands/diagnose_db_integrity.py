from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Diagnose database integrity issues that cause transaction errors'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=== Database Integrity Diagnosis ===\n'))

        with connection.cursor() as cursor:
            # Check 1: Orphaned FeaturePermissions
            self.stdout.write('1. Checking FeaturePermission -> Permission foreign keys...')
            cursor.execute("""
                SELECT fp.id, fp.feature_id, fp.permission_id
                FROM tenants_featurepermission fp
                LEFT JOIN auth_permission p ON fp.permission_id = p.id
                WHERE p.id IS NULL
            """)
            orphaned_fps = cursor.fetchall()

            if orphaned_fps:
                self.stdout.write(self.style.ERROR(f'   ❌ Found {len(orphaned_fps)} orphaned FeaturePermission records:'))
                for fp_id, feature_id, perm_id in orphaned_fps:
                    self.stdout.write(f'      FP #{fp_id}: feature_id={feature_id}, invalid permission_id={perm_id}')
            else:
                self.stdout.write(self.style.SUCCESS('   ✅ All FeaturePermission FKs are valid'))

            # Check 2: Orphaned Permissions
            self.stdout.write('\n2. Checking Permission -> ContentType foreign keys...')
            cursor.execute("""
                SELECT p.id, p.codename, p.content_type_id
                FROM auth_permission p
                LEFT JOIN django_content_type ct ON p.content_type_id = ct.id
                WHERE ct.id IS NULL
            """)
            orphaned_perms = cursor.fetchall()

            if orphaned_perms:
                self.stdout.write(self.style.ERROR(f'   ❌ Found {len(orphaned_perms)} orphaned Permission records:'))
                for perm_id, codename, ct_id in orphaned_perms:
                    self.stdout.write(f'      Permission #{perm_id} ({codename}): invalid content_type_id={ct_id}')
                self.stdout.write(self.style.WARNING('\n   This is likely the ROOT CAUSE of transaction errors!'))
            else:
                self.stdout.write(self.style.SUCCESS('   ✅ All Permission FKs are valid'))

            # Check 3: List all ContentTypes to see what exists
            self.stdout.write('\n3. Listing all ContentTypes...')
            cursor.execute("""
                SELECT id, app_label, model
                FROM django_content_type
                ORDER BY app_label, model
            """)
            content_types = cursor.fetchall()
            self.stdout.write(f'   Found {len(content_types)} ContentTypes:')
            for ct_id, app_label, model in content_types[:10]:  # Show first 10
                self.stdout.write(f'      #{ct_id}: {app_label}.{model}')
            if len(content_types) > 10:
                self.stdout.write(f'      ... and {len(content_types) - 10} more')

            # Check 4: Find permissions pointing to non-existent content types
            self.stdout.write('\n4. Detailed check of invalid permissions...')
            cursor.execute("""
                SELECT
                    p.id,
                    p.codename,
                    p.name,
                    p.content_type_id,
                    COUNT(fp.id) as feature_permission_count
                FROM auth_permission p
                LEFT JOIN django_content_type ct ON p.content_type_id = ct.id
                LEFT JOIN tenants_featurepermission fp ON fp.permission_id = p.id
                WHERE ct.id IS NULL
                GROUP BY p.id, p.codename, p.name, p.content_type_id
            """)
            invalid_perms = cursor.fetchall()

            if invalid_perms:
                self.stdout.write(self.style.ERROR(f'   Found {len(invalid_perms)} permissions with invalid content_type_id:'))
                for perm_id, codename, name, ct_id, fp_count in invalid_perms:
                    self.stdout.write(
                        f'      Permission #{perm_id} "{codename}" (name: {name}): '
                        f'points to non-existent CT #{ct_id}, '
                        f'referenced by {fp_count} FeaturePermissions'
                    )

        self.stdout.write(self.style.SUCCESS('\n=== Diagnosis complete ==='))

        if orphaned_fps or orphaned_perms:
            self.stdout.write(self.style.WARNING('\n⚠️  Database has integrity issues that need cleanup!'))
            self.stdout.write('Run: python3 manage.py cleanup_orphaned_records')
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Database integrity looks good!'))
