from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import time
from booking_management.models import (
    ServiceCategory, Service, BookingStaff, StaffAvailability,
    BookingClient, Booking
)
from users.models import User, TenantGroup


class Command(BaseCommand):
    help = 'Seed booking management with sample data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing booking data before seeding'
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing existing booking data...'))
            Booking.objects.all().delete()
            BookingClient.objects.all().delete()
            Service.objects.all().delete()
            ServiceCategory.objects.all().delete()
            StaffAvailability.objects.all().delete()
            BookingStaff.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Cleared existing data'))

        self.stdout.write('Creating booking management seed data...')

        # Create or get booking staff group
        booking_staff_group, created = TenantGroup.objects.get_or_create(
            name='Booking Staff',
            defaults={
                'description': 'Staff members who can be assigned to bookings',
                'is_booking_staff': True
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS('Created Booking Staff group'))
        else:
            # Update existing group to be booking staff
            booking_staff_group.is_booking_staff = True
            booking_staff_group.save()
            self.stdout.write('Updated existing Booking Staff group')

        # Create service categories
        categories_data = [
            {
                'name': {'en': 'Hair Services', 'ka': 'თმის მომსახურება'},
                'description': {'en': 'Professional hair care services', 'ka': 'პროფესიონალური თმის მოვლის სერვისები'}
            },
            {
                'name': {'en': 'Beauty Services', 'ka': 'სილამაზის სერვისები'},
                'description': {'en': 'Beauty and skincare treatments', 'ka': 'სილამაზისა და კანის მოვლის პროცედურები'}
            },
            {
                'name': {'en': 'Massage', 'ka': 'მასაჟი'},
                'description': {'en': 'Relaxation and therapeutic massage', 'ka': 'მოდუნების და თერაპიული მასაჟი'}
            },
        ]

        categories = []
        for cat_data in categories_data:
            category, created = ServiceCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={'description': cat_data['description']}
            )
            categories.append(category)
            if created:
                self.stdout.write(f'Created category: {cat_data["name"]["en"]}')

        # Create sample staff members
        staff_data = [
            {
                'email': 'stylist1@example.com',
                'first_name': 'Anna',
                'last_name': 'Smith',
                'specialty': 'Hair Styling'
            },
            {
                'email': 'stylist2@example.com',
                'first_name': 'Maria',
                'last_name': 'Johnson',
                'specialty': 'Beauty Treatments'
            },
            {
                'email': 'therapist1@example.com',
                'first_name': 'David',
                'last_name': 'Brown',
                'specialty': 'Massage Therapy'
            },
        ]

        staff_members = []
        for staff_info in staff_data:
            # Create or get user
            user, user_created = User.objects.get_or_create(
                email=staff_info['email'],
                defaults={
                    'first_name': staff_info['first_name'],
                    'last_name': staff_info['last_name'],
                    'role': 'agent',
                    'status': 'active'
                }
            )

            # Add user to booking staff group
            user.tenant_groups.add(booking_staff_group)

            # Create booking staff profile
            booking_staff, staff_created = BookingStaff.objects.get_or_create(
                user=user,
                defaults={
                    'specialty': staff_info['specialty'],
                    'is_active_for_bookings': True
                }
            )
            staff_members.append(booking_staff)

            if staff_created:
                self.stdout.write(f'Created staff: {staff_info["first_name"]} {staff_info["last_name"]}')

                # Create weekly availability (Monday-Friday, 9 AM - 5 PM)
                for day in range(5):  # Monday to Friday
                    StaffAvailability.objects.get_or_create(
                        staff=booking_staff,
                        day_of_week=day,
                        defaults={
                            'is_available': True,
                            'start_time': time(9, 0),
                            'end_time': time(17, 0),
                            'break_start': time(12, 0),
                            'break_end': time(13, 0)
                        }
                    )

        # Create services
        services_data = [
            {
                'name': {'en': 'Haircut & Styling', 'ka': 'თმის შეჭრა და სტაილინგი'},
                'description': {'en': 'Professional haircut with styling', 'ka': 'პროფესიონალური თმის შეჭრა სტაილინგით'},
                'category': categories[0],
                'base_price': 50.00,
                'duration_minutes': 60,
                'booking_type': 'duration_based',
                'staff': [staff_members[0], staff_members[1]]
            },
            {
                'name': {'en': 'Hair Coloring', 'ka': 'თმის შეღებვა'},
                'description': {'en': 'Full hair coloring service', 'ka': 'თმის სრული შეღებვის სერვისი'},
                'category': categories[0],
                'base_price': 120.00,
                'duration_minutes': 120,
                'deposit_percentage': 30,
                'booking_type': 'duration_based',
                'staff': [staff_members[0]]
            },
            {
                'name': {'en': 'Facial Treatment', 'ka': 'სახის პროცედურა'},
                'description': {'en': 'Deep cleansing facial', 'ka': 'სახის ღრმა გაწმენდის პროცედურა'},
                'category': categories[1],
                'base_price': 80.00,
                'duration_minutes': 90,
                'booking_type': 'fixed_slots',
                'available_time_slots': ['09:00', '11:00', '13:00', '15:00'],
                'staff': [staff_members[1]]
            },
            {
                'name': {'en': 'Swedish Massage', 'ka': 'შვედური მასაჟი'},
                'description': {'en': 'Relaxing full body massage', 'ka': 'მოდუნების სრული სხეულის მასაჟი'},
                'category': categories[2],
                'base_price': 100.00,
                'duration_minutes': 60,
                'booking_type': 'fixed_slots',
                'available_time_slots': ['09:00', '10:30', '12:00', '14:00', '15:30'],
                'staff': [staff_members[2]]
            },
            {
                'name': {'en': 'Deep Tissue Massage', 'ka': 'ღრმა ქსოვილის მასაჟი'},
                'description': {'en': 'Therapeutic deep tissue massage', 'ka': 'თერაპიული ღრმა ქსოვილის მასაჟი'},
                'category': categories[2],
                'base_price': 120.00,
                'duration_minutes': 90,
                'deposit_percentage': 20,
                'booking_type': 'duration_based',
                'staff': [staff_members[2]]
            },
        ]

        services = []
        for service_data in services_data:
            staff_to_assign = service_data.pop('staff')

            service, created = Service.objects.get_or_create(
                name=service_data['name'],
                defaults=service_data
            )

            # Assign staff members
            service.staff_members.set(staff_to_assign)
            services.append(service)

            if created:
                self.stdout.write(f'Created service: {service_data["name"]["en"]}')

        # Create sample booking clients
        clients_data = [
            {
                'email': 'client1@example.com',
                'first_name': 'John',
                'last_name': 'Doe',
                'phone_number': '+995555111222'
            },
            {
                'email': 'client2@example.com',
                'first_name': 'Jane',
                'last_name': 'Wilson',
                'phone_number': '+995555333444'
            },
        ]

        for client_info in clients_data:
            client, created = BookingClient.objects.get_or_create(
                email=client_info['email'],
                defaults={
                    **client_info,
                    'is_verified': True
                }
            )
            if created:
                client.set_password('password123')
                client.save()
                self.stdout.write(f'Created client: {client_info["email"]}')

        self.stdout.write(self.style.SUCCESS('\nBooking management seed data created successfully!'))
        self.stdout.write(self.style.SUCCESS(f'Created {len(categories)} categories'))
        self.stdout.write(self.style.SUCCESS(f'Created {len(staff_members)} staff members'))
        self.stdout.write(self.style.SUCCESS(f'Created {len(services)} services'))
        self.stdout.write(self.style.SUCCESS(f'Created {len(clients_data)} sample clients'))
        self.stdout.write('\nSample client login:')
        self.stdout.write('  Email: client1@example.com')
        self.stdout.write('  Password: password123')
