from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import random
import uuid

from crm.models import CallLog, CallEvent, CallRecording, SipConfiguration, Client

User = get_user_model()


class Command(BaseCommand):
    help = 'Test call logging functionality with sample data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=10,
            help='Number of test calls to create'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Clean up existing test data first'
        )

    def handle(self, *args, **options):
        if options['cleanup']:
            self.stdout.write('Cleaning up existing test data...')
            CallLog.objects.filter(notes__startswith='[TEST]').delete()
            self.stdout.write(self.style.SUCCESS('Cleaned up test data'))

        # Get or create a test user
        user, created = User.objects.get_or_create(
            email='test@example.com',
            defaults={
                'first_name': 'Test',
                'last_name': 'User'
            }
        )

        # Get or create a SIP configuration
        sip_config, created = SipConfiguration.objects.get_or_create(
            name='Test SIP Config',
            defaults={
                'sip_server': 'test.sip.server.com',
                'username': 'testuser',
                'password': 'testpass',
                'created_by': user,
                'is_default': True
            }
        )

        # Create some test clients
        test_clients = []
        for i in range(3):
            client, created = Client.objects.get_or_create(
                email=f'client{i}@example.com',
                defaults={
                    'name': f'Test Client {i}',
                    'phone': f'+1555000{i:03d}',
                    'company': f'Test Company {i}'
                }
            )
            test_clients.append(client)

        count = options['count']
        self.stdout.write(f'Creating {count} test calls...')

        call_statuses = ['answered', 'missed', 'ended', 'failed', 'busy']
        directions = ['inbound', 'outbound']
        phone_numbers = ['+15551234567', '+15559876543', '+15555551234', '+15554567890']

        for i in range(count):
            direction = random.choice(directions)
            status = random.choice(call_statuses)
            
            # Generate call timing
            started_at = timezone.now() - timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            answered_at = None
            ended_at = None
            duration = None
            
            if status in ['answered', 'ended']:
                answered_at = started_at + timedelta(seconds=random.randint(5, 30))
                ended_at = answered_at + timedelta(seconds=random.randint(30, 3600))
                duration = ended_at - answered_at

            caller_number = random.choice(phone_numbers) if direction == 'inbound' else sip_config.username
            recipient_number = sip_config.username if direction == 'inbound' else random.choice(phone_numbers)

            # Create call log
            call_log = CallLog.objects.create(
                caller_number=caller_number,
                recipient_number=recipient_number,
                direction=direction,
                status=status,
                started_at=started_at,
                answered_at=answered_at,
                ended_at=ended_at,
                duration=duration,
                handled_by=user,
                sip_configuration=sip_config,
                client=random.choice(test_clients) if random.random() > 0.3 else None,
                sip_call_id=str(uuid.uuid4()),
                notes=f'[TEST] Sample call {i+1}',
                call_quality_score=random.uniform(3.0, 5.0) if status == 'answered' else None
            )

            # Create call events
            events = ['initiated', 'ringing']
            if status in ['answered', 'ended']:
                events.append('answered')
            
            if status == 'ended':
                events.extend(['ended'])
            elif status == 'missed':
                events.extend(['missed'])
            elif status == 'failed':
                events.extend(['failed'])

            for j, event_type in enumerate(events):
                event_time = started_at + timedelta(seconds=j*5)
                CallEvent.objects.create(
                    call_log=call_log,
                    event_type=event_type,
                    timestamp=event_time,
                    user=user,
                    metadata={
                        'test_event': True,
                        'sequence': j
                    }
                )

            # Create recording for some answered calls
            if status in ['answered', 'ended'] and random.random() > 0.5:
                recording = CallRecording.objects.create(
                    call_log=call_log,
                    status='completed',
                    file_path=f'/recordings/test_call_{call_log.call_id}.wav',
                    file_size=random.randint(100000, 5000000),
                    duration=duration,
                    format='wav',
                    started_at=answered_at,
                    completed_at=ended_at
                )
                
                # Add recording events
                CallEvent.objects.create(
                    call_log=call_log,
                    event_type='recording_started',
                    timestamp=answered_at + timedelta(seconds=10),
                    user=user,
                    metadata={'recording_id': str(recording.recording_id)}
                )
                
                CallEvent.objects.create(
                    call_log=call_log,
                    event_type='recording_stopped',
                    timestamp=ended_at,
                    user=user,
                    metadata={'recording_id': str(recording.recording_id)}
                )

            if (i + 1) % 5 == 0:
                self.stdout.write(f'Created {i + 1} calls...')

        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {count} test calls with events and recordings')
        )
        
        # Print summary
        self.stdout.write('\n--- Call Summary ---')
        total_calls = CallLog.objects.filter(notes__startswith='[TEST]').count()
        answered_calls = CallLog.objects.filter(notes__startswith='[TEST]', status='answered').count()
        recordings = CallRecording.objects.filter(call_log__notes__startswith='[TEST]').count()
        events = CallEvent.objects.filter(call_log__notes__startswith='[TEST]').count()
        
        self.stdout.write(f'Total test calls: {total_calls}')
        self.stdout.write(f'Answered calls: {answered_calls}')
        self.stdout.write(f'Recordings: {recordings}')
        self.stdout.write(f'Events: {events}')
