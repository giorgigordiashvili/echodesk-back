from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tenants', '0046_security_log_user_id_fix'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paymentattempt',
            name='bog_error_code',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]
