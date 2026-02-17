"""
Set DB-level default for is_echo columns on FacebookMessage and InstagramMessage.

Django's AddField sets NOT NULL but removes the DB-level DEFAULT after migration.
This causes errors when older code (without explicit is_echo=False) inserts rows.
This migration adds a permanent DB-level DEFAULT false to prevent NULL violations.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('social_integrations', '0034_message_source_author_tracking'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE social_integrations_facebookmessage ALTER COLUMN is_echo SET DEFAULT false;",
            reverse_sql="ALTER TABLE social_integrations_facebookmessage ALTER COLUMN is_echo DROP DEFAULT;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE social_integrations_instagrammessage ALTER COLUMN is_echo SET DEFAULT false;",
            reverse_sql="ALTER TABLE social_integrations_instagrammessage ALTER COLUMN is_echo DROP DEFAULT;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE social_integrations_facebookmessage ALTER COLUMN source SET DEFAULT 'echodesk';",
            reverse_sql="ALTER TABLE social_integrations_facebookmessage ALTER COLUMN source DROP DEFAULT;",
        ),
        migrations.RunSQL(
            sql="ALTER TABLE social_integrations_instagrammessage ALTER COLUMN source SET DEFAULT 'echodesk';",
            reverse_sql="ALTER TABLE social_integrations_instagrammessage ALTER COLUMN source DROP DEFAULT;",
        ),
    ]
