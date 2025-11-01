# Generated manually

from django.db import migrations


def seed_default_languages(apps, schema_editor):
    """Seed default languages: English and Georgian"""
    Language = apps.get_model('ecommerce_crm', 'Language')

    # Create English language
    Language.objects.get_or_create(
        code='en',
        defaults={
            'name': {'en': 'English', 'ka': 'ინგლისური'},
            'is_default': True,
            'is_active': True,
            'sort_order': 1
        }
    )

    # Create Georgian language
    Language.objects.get_or_create(
        code='ka',
        defaults={
            'name': {'en': 'Georgian', 'ka': 'ქართული'},
            'is_default': True,
            'is_active': True,
            'sort_order': 2
        }
    )


def remove_default_languages(apps, schema_editor):
    """Remove default languages on migration rollback"""
    Language = apps.get_model('ecommerce_crm', 'Language')
    Language.objects.filter(code__in=['en', 'ka']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce_crm', '0003_language'),
    ]

    operations = [
        migrations.RunPython(seed_default_languages, remove_default_languages),
    ]
