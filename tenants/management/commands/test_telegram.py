"""
Test Telegram Bot Connection

Tests the Telegram bot configuration and sends a test message.

Usage:
    python manage.py test_telegram
"""
from django.core.management.base import BaseCommand
from tenants.telegram_notifications import test_telegram_connection


class Command(BaseCommand):
    help = 'Test Telegram bot connection and send a test message'

    def handle(self, *args, **options):
        self.stdout.write('Testing Telegram bot connection...')
        self.stdout.write('')

        result = test_telegram_connection()

        if result['success']:
            self.stdout.write(self.style.SUCCESS(f"✓ {result['message']}"))
            self.stdout.write('')
            self.stdout.write('Check your Telegram to see the test message!')
        else:
            self.stdout.write(self.style.ERROR(f"✗ {result['message']}"))
            self.stdout.write('')
            self.stdout.write('Please check your configuration:')
            self.stdout.write('  1. TELEGRAM_BOT_TOKEN in .env file')
            self.stdout.write('  2. TELEGRAM_CHAT_ID in .env file')
