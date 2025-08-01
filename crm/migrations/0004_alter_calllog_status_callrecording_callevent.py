# Generated by Django 4.2.16 on 2025-07-26 17:35

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('crm', '0003_add_call_id_unique_constraint'),
    ]

    operations = [
        migrations.AlterField(
            model_name='calllog',
            name='status',
            field=models.CharField(choices=[('initiated', 'Initiated'), ('ringing', 'Ringing'), ('answered', 'Answered'), ('missed', 'Missed'), ('busy', 'Busy'), ('no_answer', 'No Answer'), ('failed', 'Failed'), ('cancelled', 'Cancelled'), ('transferred', 'Transferred'), ('ended', 'Ended'), ('recording', 'Recording'), ('on_hold', 'On Hold')], default='ringing', max_length=20),
        ),
        migrations.CreateModel(
            name='CallRecording',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recording_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('file_path', models.CharField(blank=True, help_text='Local file path', max_length=500)),
                ('file_url', models.URLField(blank=True, help_text='External URL for recording')),
                ('file_size', models.BigIntegerField(blank=True, help_text='File size in bytes', null=True)),
                ('duration', models.DurationField(blank=True, help_text='Recording duration', null=True)),
                ('format', models.CharField(default='wav', help_text='Audio format', max_length=10)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('recording', 'Recording'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed'), ('deleted', 'Deleted')], default='pending', max_length=15)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('transcript', models.TextField(blank=True, help_text='Call transcript')),
                ('transcript_confidence', models.FloatField(blank=True, help_text='Transcript confidence (0-1)', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('call_log', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='recording', to='crm.calllog')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='CallEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('initiated', 'Call Initiated'), ('ringing', 'Ringing Started'), ('answered', 'Call Answered'), ('hold', 'Call On Hold'), ('unhold', 'Call Resumed'), ('transfer_initiated', 'Transfer Initiated'), ('transfer_completed', 'Transfer Completed'), ('recording_started', 'Recording Started'), ('recording_stopped', 'Recording Stopped'), ('muted', 'Call Muted'), ('unmuted', 'Call Unmuted'), ('dtmf', 'DTMF Pressed'), ('quality_change', 'Call Quality Changed'), ('ended', 'Call Ended'), ('failed', 'Call Failed'), ('error', 'Error Occurred')], max_length=20)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional event data')),
                ('call_log', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='events', to='crm.calllog')),
                ('user', models.ForeignKey(blank=True, help_text='User who triggered this event', null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['timestamp'],
                'indexes': [models.Index(fields=['call_log', 'event_type'], name='crm_calleve_call_lo_c5ed15_idx'), models.Index(fields=['timestamp'], name='crm_calleve_timesta_815be8_idx')],
            },
        ),
    ]
