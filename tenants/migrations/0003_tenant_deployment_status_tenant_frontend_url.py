# Generated by Django 4.2.16 on 2025-07-25 14:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0002_tenant_preferred_language'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='deployment_status',
            field=models.CharField(choices=[('pending', 'Pending'), ('deploying', 'Deploying'), ('deployed', 'Deployed'), ('failed', 'Failed')], default='pending', help_text='Status of the frontend deployment', max_length=20),
        ),
        migrations.AddField(
            model_name='tenant',
            name='frontend_url',
            field=models.URLField(blank=True, help_text='URL of the deployed frontend', null=True),
        ),
    ]
