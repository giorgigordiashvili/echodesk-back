# Generated by Django 4.2.16 on 2025-07-25 22:23

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('crm', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SipConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Configuration name', max_length=100)),
                ('sip_server', models.CharField(help_text='SIP server hostname/IP', max_length=255)),
                ('sip_port', models.IntegerField(default=5060, help_text='SIP server port')),
                ('username', models.CharField(help_text='SIP username', max_length=100)),
                ('password', models.CharField(help_text='SIP password', max_length=255)),
                ('realm', models.CharField(blank=True, help_text='SIP realm/domain', max_length=255)),
                ('proxy', models.CharField(blank=True, help_text='Outbound proxy', max_length=255)),
                ('stun_server', models.CharField(blank=True, default='stun:stun.l.google.com:19302', help_text='STUN server for NAT traversal', max_length=255)),
                ('turn_server', models.CharField(blank=True, help_text='TURN server', max_length=255)),
                ('turn_username', models.CharField(blank=True, max_length=100)),
                ('turn_password', models.CharField(blank=True, max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('is_default', models.BooleanField(default=False)),
                ('max_concurrent_calls', models.IntegerField(default=5)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-is_default', 'name'],
            },
        ),
        migrations.AlterModelOptions(
            name='calllog',
            options={'ordering': ['-started_at']},
        ),
        migrations.AddField(
            model_name='calllog',
            name='answered_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='calllog',
            name='call_id',
            field=models.UUIDField(default=uuid.uuid4, editable=False),
        ),
        migrations.AddField(
            model_name='calllog',
            name='call_quality_score',
            field=models.FloatField(blank=True, help_text='Call quality (0-5)', null=True),
        ),
        migrations.AddField(
            model_name='calllog',
            name='call_type',
            field=models.CharField(choices=[('voice', 'Voice Call'), ('video', 'Video Call'), ('conference', 'Conference Call')], default='voice', max_length=15),
        ),
        migrations.AddField(
            model_name='calllog',
            name='client',
            field=models.ForeignKey(blank=True, help_text='Associated client (auto-detected by phone number)', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='calls', to='crm.client'),
        ),
        migrations.AddField(
            model_name='calllog',
            name='direction',
            field=models.CharField(choices=[('inbound', 'Inbound'), ('outbound', 'Outbound')], default='inbound', max_length=10),
        ),
        migrations.AddField(
            model_name='calllog',
            name='ended_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='calllog',
            name='recording_url',
            field=models.URLField(blank=True, help_text='Call recording file URL'),
        ),
        migrations.AddField(
            model_name='calllog',
            name='sip_call_id',
            field=models.CharField(blank=True, help_text='SIP Call-ID header', max_length=255),
        ),
        migrations.AddField(
            model_name='calllog',
            name='started_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='calllog',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name='calllog',
            name='status',
            field=models.CharField(choices=[('ringing', 'Ringing'), ('answered', 'Answered'), ('missed', 'Missed'), ('busy', 'Busy'), ('no_answer', 'No Answer'), ('failed', 'Failed'), ('cancelled', 'Cancelled'), ('transferred', 'Transferred'), ('ended', 'Ended')], default='ringing', max_length=20),
        ),
        migrations.AddIndex(
            model_name='calllog',
            index=models.Index(fields=['caller_number'], name='crm_calllog_caller__28c2c5_idx'),
        ),
        migrations.AddIndex(
            model_name='calllog',
            index=models.Index(fields=['recipient_number'], name='crm_calllog_recipie_8f57c0_idx'),
        ),
        migrations.AddIndex(
            model_name='calllog',
            index=models.Index(fields=['status'], name='crm_calllog_status_c4a6ea_idx'),
        ),
        migrations.AddIndex(
            model_name='calllog',
            index=models.Index(fields=['direction'], name='crm_calllog_directi_61961f_idx'),
        ),
        migrations.AddIndex(
            model_name='calllog',
            index=models.Index(fields=['started_at'], name='crm_calllog_started_31f784_idx'),
        ),
        migrations.AddField(
            model_name='sipconfiguration',
            name='created_by',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='created_sip_configs', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='calllog',
            name='sip_configuration',
            field=models.ForeignKey(blank=True, help_text='SIP configuration used for this call', null=True, on_delete=django.db.models.deletion.SET_NULL, to='crm.sipconfiguration'),
        ),
    ]
