# Generated manually to rename the widget notification sound field so it
# follows the `notification_sound_<platform>` convention used by every
# other per-platform sound on SocialIntegrationSettings. The field was
# only shipped in PR 1 and defaults to 'default', so any tenant that
# hasn't yet customised it keeps the default after the rename.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('social_integrations', '0050_socialintegrationsettings_widget_enabled_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='socialintegrationsettings',
            old_name='widget_notification_sound',
            new_name='notification_sound_widget',
        ),
    ]
