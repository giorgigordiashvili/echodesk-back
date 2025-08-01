# Generated by Django 4.2.16 on 2025-08-01 19:33

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('social_integrations', '0002_instagramaccountconnection_instagrammessage'),
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsAppBusinessConnection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('business_account_id', models.CharField(max_length=255)),
                ('phone_number_id', models.CharField(max_length=255)),
                ('phone_number', models.CharField(max_length=20)),
                ('display_phone_number', models.CharField(max_length=20)),
                ('verified_name', models.CharField(max_length=255)),
                ('access_token', models.TextField()),
                ('webhook_url', models.URLField(blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='whatsapp_connections', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'phone_number_id')},
            },
        ),
        migrations.CreateModel(
            name='WhatsAppMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_id', models.CharField(max_length=255, unique=True)),
                ('from_number', models.CharField(max_length=20)),
                ('to_number', models.CharField(max_length=20)),
                ('contact_name', models.CharField(blank=True, max_length=255)),
                ('message_text', models.TextField(blank=True)),
                ('message_type', models.CharField(default='text', max_length=50)),
                ('media_url', models.URLField(blank=True)),
                ('media_mime_type', models.CharField(blank=True, max_length=100)),
                ('timestamp', models.DateTimeField()),
                ('is_from_business', models.BooleanField(default=False)),
                ('is_read', models.BooleanField(default=False)),
                ('delivery_status', models.CharField(default='sent', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('connection', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='social_integrations.whatsappbusinessconnection')),
            ],
            options={
                'ordering': ['-timestamp'],
            },
        ),
    ]
