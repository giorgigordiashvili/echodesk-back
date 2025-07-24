from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()


class Command(BaseCommand):
    help = 'Create a superuser for the admin panel'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Admin email address')
        parser.add_argument('--password', type=str, help='Admin password')

    def handle(self, *args, **options):
        email = options.get('email') or os.getenv('ADMIN_EMAIL', 'admin@amanati.com')
        password = options.get('password') or os.getenv('ADMIN_PASSWORD', 'admin123')

        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f'User with email {email} already exists.')
            )
            return

        User.objects.create_superuser(
            email=email,
            password=password,
            first_name='Admin',
            last_name='User'
        )

        self.stdout.write(
            self.style.SUCCESS(f'Superuser created successfully with email: {email}')
        )
        self.stdout.write(
            self.style.SUCCESS('You can now access the admin panel at /admin/')
        )
