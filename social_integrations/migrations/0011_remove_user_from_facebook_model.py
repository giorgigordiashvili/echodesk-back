# Generated manually to fix FacebookPageConnection model mismatch
# This aligns with the multi-tenant architecture where tenant schema provides isolation
# instead of user-based isolation (similar to 0007_remove_user_from_instagram_model.py)

from django.db import migrations
from django.db import connection


def remove_user_field_if_exists(apps, schema_editor):
    """
    Remove user field from FacebookPageConnection if it exists.
    This handles cases where the field may or may not exist in the database.
    """
    with connection.cursor() as cursor:
        # Check if the user_id column exists in the table
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='social_integrations_facebookpageconnection' 
            AND column_name='user_id'
            AND table_schema='public';
        """)
        
        if cursor.fetchone():
            # Column exists, so remove it
            cursor.execute("""
                ALTER TABLE social_integrations_facebookpageconnection 
                DROP COLUMN user_id CASCADE;
            """)
            
        # Also remove any unique constraints that might reference user
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name='social_integrations_facebookpageconnection'
            AND constraint_type='UNIQUE'
            AND table_schema='public';
        """)
        
        constraints = cursor.fetchall()
        for constraint in constraints:
            try:
                cursor.execute(f"""
                    ALTER TABLE social_integrations_facebookpageconnection 
                    DROP CONSTRAINT {constraint[0]};
                """)
            except:
                # Constraint might not exist or already dropped
                pass


def reverse_remove_user_field(apps, schema_editor):
    """
    This is irreversible since we don't know the original state
    """
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('social_integrations', '0010_alter_instagrammessage_message_id'),
    ]

    operations = [
        migrations.RunPython(remove_user_field_if_exists, reverse_remove_user_field),
    ]