from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = 'Clean up orphaned Permission and FeaturePermission records using raw SQL'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=== Cleaning Up Orphaned Records ===\n'))

        with transaction.atomic():
            with connection.cursor() as cursor:
                # Step 1: Find and delete FeaturePermissions pointing to non-existent Permissions
                self.stdout.write('1. Cleaning orphaned FeaturePermission records...')
                cursor.execute("""
                    SELECT COUNT(*) FROM tenants_featurepermission fp
                    LEFT JOIN auth_permission p ON fp.permission_id = p.id
                    WHERE p.id IS NULL
                """)
                orphaned_fp_count = cursor.fetchone()[0]

                if orphaned_fp_count > 0:
                    self.stdout.write(self.style.WARNING(f'   Found {orphaned_fp_count} orphaned FeaturePermission records'))
                    cursor.execute("""
                        DELETE FROM tenants_featurepermission
                        WHERE permission_id NOT IN (SELECT id FROM auth_permission)
                    """)
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Deleted {orphaned_fp_count} FeaturePermission records'))
                else:
                    self.stdout.write(self.style.SUCCESS('   ✅ No orphaned FeaturePermission records'))

                # Step 2: Find and delete Permissions pointing to non-existent ContentTypes
                self.stdout.write('\n2. Cleaning orphaned Permission records...')
                cursor.execute("""
                    SELECT COUNT(*) FROM auth_permission p
                    LEFT JOIN django_content_type ct ON p.content_type_id = ct.id
                    WHERE ct.id IS NULL
                """)
                orphaned_perm_count = cursor.fetchone()[0]

                if orphaned_perm_count > 0:
                    self.stdout.write(self.style.WARNING(f'   Found {orphaned_perm_count} orphaned Permission records'))
                    self.stdout.write(self.style.WARNING('   These are the root cause of the admin errors!'))

                    # First delete any FeaturePermissions pointing to these permissions
                    cursor.execute("""
                        DELETE FROM tenants_featurepermission
                        WHERE permission_id IN (
                            SELECT p.id FROM auth_permission p
                            LEFT JOIN django_content_type ct ON p.content_type_id = ct.id
                            WHERE ct.id IS NULL
                        )
                    """)

                    # Then delete the orphaned permissions
                    cursor.execute("""
                        DELETE FROM auth_permission
                        WHERE content_type_id NOT IN (SELECT id FROM django_content_type)
                    """)
                    self.stdout.write(self.style.SUCCESS(f'   ✅ Deleted {orphaned_perm_count} Permission records'))
                else:
                    self.stdout.write(self.style.SUCCESS('   ✅ No orphaned Permission records'))

                # Step 3: Verify cleanup
                self.stdout.write('\n3. Verifying cleanup...')
                cursor.execute("""
                    SELECT COUNT(*) FROM tenants_featurepermission fp
                    LEFT JOIN auth_permission p ON fp.permission_id = p.id
                    WHERE p.id IS NULL
                """)
                remaining_fp = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT COUNT(*) FROM auth_permission p
                    LEFT JOIN django_content_type ct ON p.content_type_id = ct.id
                    WHERE ct.id IS NULL
                """)
                remaining_perm = cursor.fetchone()[0]

                if remaining_fp == 0 and remaining_perm == 0:
                    self.stdout.write(self.style.SUCCESS('   ✅ All orphaned records cleaned up!'))
                    self.stdout.write(self.style.SUCCESS('\n=== Admin should now work correctly ==='))
                else:
                    self.stdout.write(self.style.ERROR(f'   ❌ Still have issues: {remaining_fp} FPs, {remaining_perm} Permissions'))
