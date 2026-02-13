# Data migration to merge BookingClient data into unified Client model

from django.db import migrations


def migrate_booking_clients_forward(apps, schema_editor):
    """
    Migrate BookingClient data to unified Client model.
    - If a Client with the same email exists, merge booking fields into it
    - If not, create a new Client with booking data enabled
    """
    # Get models using the historical versions
    Client = apps.get_model('social_integrations', 'Client')

    try:
        BookingClient = apps.get_model('booking_management', 'BookingClient')
    except LookupError:
        # BookingClient model doesn't exist yet or already removed
        return

    for booking_client in BookingClient.objects.all():
        # Try to find existing Client with same email
        existing_client = None
        if booking_client.email:
            existing_client = Client.objects.filter(email=booking_client.email).first()

        if existing_client:
            # Merge booking fields into existing client
            existing_client.first_name = booking_client.first_name
            existing_client.last_name = booking_client.last_name
            existing_client.password_hash = booking_client.password_hash
            existing_client.is_booking_enabled = True
            existing_client.is_verified = booking_client.is_verified
            existing_client.verification_token = booking_client.verification_token
            existing_client.verification_sent_at = booking_client.verification_sent_at
            existing_client.reset_token = booking_client.reset_token
            existing_client.reset_token_expires = booking_client.reset_token_expires
            existing_client.last_login = booking_client.last_login
            # Update phone if not already set
            if not existing_client.phone and booking_client.phone_number:
                existing_client.phone = booking_client.phone_number
            existing_client.save()

            # Store the mapping for FK migration
            # We'll need to update Booking and RecurringBooking to point to this client
            booking_client._new_client_id = existing_client.id
        else:
            # Create new Client with booking data
            full_name = f"{booking_client.first_name} {booking_client.last_name}".strip()
            new_client = Client.objects.create(
                name=full_name or booking_client.email,
                email=booking_client.email,
                phone=booking_client.phone_number,
                first_name=booking_client.first_name,
                last_name=booking_client.last_name,
                password_hash=booking_client.password_hash,
                is_booking_enabled=True,
                is_verified=booking_client.is_verified,
                verification_token=booking_client.verification_token,
                verification_sent_at=booking_client.verification_sent_at,
                reset_token=booking_client.reset_token,
                reset_token_expires=booking_client.reset_token_expires,
                last_login=booking_client.last_login,
            )
            booking_client._new_client_id = new_client.id


def migrate_booking_clients_reverse(apps, schema_editor):
    """
    Reverse migration - not fully reversible since we're merging data
    This will just disable booking on clients that were created from BookingClient
    """
    Client = apps.get_model('social_integrations', 'Client')
    # Just mark as not booking enabled
    Client.objects.filter(is_booking_enabled=True).update(is_booking_enabled=False)


class Migration(migrations.Migration):

    dependencies = [
        ('social_integrations', '0029_rename_socialclient_to_client'),
        ('booking_management', '0002_alter_bookingstaff_profile_image_alter_service_image'),
    ]

    operations = [
        migrations.RunPython(
            migrate_booking_clients_forward,
            migrate_booking_clients_reverse,
        ),
    ]
