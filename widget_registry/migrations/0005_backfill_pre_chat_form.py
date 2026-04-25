"""Data migration: backfill empty `pre_chat_form` rows.

Existing `WidgetConnection` rows created before the new default
(``_default_pre_chat_form``) was applied have ``pre_chat_form == {}``,
which the embeddable widget treats as "form disabled". Backfill them
with the new default so admins don't have to toggle it on by hand.

Forwards is idempotent; reverse is a noop because we don't want to
clear customer-configured values when downgrading.
"""
from django.db import migrations


_DEFAULT_PRE_CHAT_FORM = {
    'enabled': True,
    'name_required': True,
    'email_required': False,
}


def backfill_pre_chat_form(apps, schema_editor):
    WidgetConnection = apps.get_model('widget_registry', 'WidgetConnection')
    # Only touch rows where the JSON is empty / unset. Don't clobber any
    # connection where the tenant has already saved a value.
    updated = 0
    for conn in WidgetConnection.objects.all().only('id', 'pre_chat_form'):
        if conn.pre_chat_form in (None, {}, ''):
            conn.pre_chat_form = dict(_DEFAULT_PRE_CHAT_FORM)
            conn.save(update_fields=['pre_chat_form'])
            updated += 1
    if updated:
        print(f"\n  Backfilled pre_chat_form on {updated} WidgetConnection row(s)")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('widget_registry', '0004_alter_widgetconnection_pre_chat_form'),
    ]

    operations = [
        migrations.RunPython(backfill_pre_chat_form, noop),
    ]
