# Generated migration for unifying BookingClient and SocialClient

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('social_integrations', '0028_add_reaction_and_reply_fields'),
    ]

    operations = [
        # Step 1: Add new booking fields to SocialClient
        migrations.AddField(
            model_name='socialclient',
            name='first_name',
            field=models.CharField(blank=True, help_text='First name for booking', max_length=100),
        ),
        migrations.AddField(
            model_name='socialclient',
            name='last_name',
            field=models.CharField(blank=True, help_text='Last name for booking', max_length=100),
        ),
        migrations.AddField(
            model_name='socialclient',
            name='password_hash',
            field=models.CharField(blank=True, help_text='Hashed password for booking auth', max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='socialclient',
            name='is_booking_enabled',
            field=models.BooleanField(default=False, help_text='Whether this client can use booking system'),
        ),
        migrations.AddField(
            model_name='socialclient',
            name='is_verified',
            field=models.BooleanField(default=False, help_text='Email verified for booking'),
        ),
        migrations.AddField(
            model_name='socialclient',
            name='verification_token',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='socialclient',
            name='verification_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='socialclient',
            name='reset_token',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='socialclient',
            name='reset_token_expires',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='socialclient',
            name='last_login',
            field=models.DateTimeField(blank=True, null=True),
        ),
        # Step 2: Add index on is_booking_enabled
        migrations.AddIndex(
            model_name='socialclient',
            index=models.Index(fields=['is_booking_enabled'], name='social_inte_is_book_b4e8f3_idx'),
        ),
        # Step 3: Rename SocialClient to Client
        migrations.RenameModel(
            old_name='SocialClient',
            new_name='Client',
        ),
        # Step 4: Update related_name on created_by to reflect new model name
        migrations.AlterField(
            model_name='client',
            name='created_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name='created_clients',
                to='users.user',
            ),
        ),
        # Step 5: Update verbose names
        migrations.AlterModelOptions(
            name='client',
            options={'ordering': ['-updated_at'], 'verbose_name': 'Client', 'verbose_name_plural': 'Clients'},
        ),
    ]
