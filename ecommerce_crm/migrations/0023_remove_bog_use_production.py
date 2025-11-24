# Generated manually

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('ecommerce_crm', '0022_add_theme_configuration'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='ecommercesettings',
            name='bog_use_production',
        ),
    ]
