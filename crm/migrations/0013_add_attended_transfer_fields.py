from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0012_add_queue_position_sounds'),
    ]

    operations = [
        migrations.AddField(
            model_name='calllog',
            name='parent_call',
            field=models.ForeignKey(
                blank=True,
                help_text='Original call this consultation was created for',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='consultation_calls',
                to='crm.calllog',
            ),
        ),
        migrations.AddField(
            model_name='calllog',
            name='transfer_type',
            field=models.CharField(
                blank=True,
                choices=[('', 'None'), ('blind', 'Blind'), ('attended', 'Attended')],
                default='',
                help_text='Type of transfer',
                max_length=10,
            ),
        ),
    ]
