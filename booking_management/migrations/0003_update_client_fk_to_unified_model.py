# Migration to update Booking and RecurringBooking FK to unified Client model

from django.db import migrations, models
import django.db.models.deletion


def migrate_booking_fks_forward(apps, schema_editor):
    """
    Update Booking and RecurringBooking foreign keys to point to the new unified Client model.
    This should run after the BookingClient data has been migrated to Client.
    """
    Booking = apps.get_model('booking_management', 'Booking')
    RecurringBooking = apps.get_model('booking_management', 'RecurringBooking')
    Client = apps.get_model('social_integrations', 'Client')

    try:
        BookingClient = apps.get_model('booking_management', 'BookingClient')
    except LookupError:
        # BookingClient already removed
        return

    # Create a mapping from old BookingClient id to new Client id
    booking_client_to_client = {}

    for bc in BookingClient.objects.all():
        # Find the corresponding Client (by email match or created during data migration)
        if bc.email:
            client = Client.objects.filter(
                email=bc.email,
                is_booking_enabled=True
            ).first()
            if client:
                booking_client_to_client[bc.id] = client.id

    # Update Booking records
    for booking in Booking.objects.all():
        old_client_id = booking.client_id
        if old_client_id in booking_client_to_client:
            # Direct SQL update to avoid model validation issues during migration
            Booking.objects.filter(id=booking.id).update(
                client_id=booking_client_to_client[old_client_id]
            )

    # Update RecurringBooking records
    for recurring in RecurringBooking.objects.all():
        old_client_id = recurring.client_id
        if old_client_id in booking_client_to_client:
            RecurringBooking.objects.filter(id=recurring.id).update(
                client_id=booking_client_to_client[old_client_id]
            )


def migrate_booking_fks_reverse(apps, schema_editor):
    """
    Reverse migration - recreate BookingClient records from Client data.
    """
    # This is a complex reverse migration that would need to recreate BookingClient
    # For now, we'll raise an error as this migration is not easily reversible
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('booking_management', '0002_alter_bookingstaff_profile_image_alter_service_image'),
        ('social_integrations', '0030_migrate_booking_clients'),
    ]

    operations = [
        # Run the data migration to update FKs
        migrations.RunPython(
            migrate_booking_fks_forward,
            migrate_booking_fks_reverse,
        ),
        # Update the Booking.client FK to point to social_integrations.Client
        migrations.AlterField(
            model_name='booking',
            name='client',
            field=models.ForeignKey(
                help_text='Client who made the booking',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='bookings',
                to='social_integrations.client',
            ),
        ),
        # Update the RecurringBooking.client FK to point to social_integrations.Client
        migrations.AlterField(
            model_name='recurringbooking',
            name='client',
            field=models.ForeignKey(
                help_text='Client with recurring booking',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='recurring_bookings',
                to='social_integrations.client',
            ),
        ),
    ]
