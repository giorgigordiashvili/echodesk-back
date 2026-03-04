"""
Data migration to unarchive email conversations that don't belong to INBOX.
Only INBOX email threads should be archivable.
"""
from django.db import migrations


def unarchive_non_inbox_emails(apps, schema_editor):
    ConversationArchive = apps.get_model('social_integrations', 'ConversationArchive')
    EmailMessage = apps.get_model('social_integrations', 'EmailMessage')

    # Get all archived email conversation thread_ids
    archived_emails = ConversationArchive.objects.filter(platform='email')

    to_delete_ids = []
    for archive in archived_emails:
        thread_id = archive.conversation_id
        account_id = archive.account_id

        # Check if this thread has any INBOX messages
        has_inbox = EmailMessage.objects.filter(
            connection_id=account_id,
            thread_id=thread_id,
            folder='INBOX'
        ).exists()

        # If thread has no INBOX messages, it shouldn't be archived
        if not has_inbox:
            to_delete_ids.append(archive.id)

    if to_delete_ids:
        deleted_count = ConversationArchive.objects.filter(id__in=to_delete_ids).delete()[0]
        print(f"\n  Unarchived {deleted_count} non-INBOX email conversations")
    else:
        print("\n  No non-INBOX email conversations to unarchive")


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('social_integrations', '0039_emailconnectionuserassignment'),
    ]

    operations = [
        migrations.RunPython(unarchive_non_inbox_emails, noop),
    ]
