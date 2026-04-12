"""Tests for CRM models: creation, save logic, custom methods, and constraints."""
from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from django.db import IntegrityError
from crm.models import (
    SipConfiguration, UserPhoneAssignment, CallLog, CallEvent,
    CallRecording, PbxSettings, Client,
)
from crm.tests.conftest import CrmTestCase


# ============================================================================
# SipConfiguration
# ============================================================================


class TestSipConfiguration(CrmTestCase):

    def test_creation(self):
        config = self.create_sip_config(name='Office PBX')
        self.assertEqual(config.name, 'Office PBX')
        self.assertEqual(config.sip_server, 'pbx.test.com')
        self.assertTrue(config.is_active)
        self.assertFalse(config.is_default)

    def test_str_representation(self):
        config = self.create_sip_config(name='Office PBX', sip_server='sip.example.com')
        self.assertEqual(str(config), 'Office PBX (sip.example.com)')

    def test_is_default_uniqueness(self):
        """Only one SIP configuration should be default per tenant."""
        admin = self.create_admin()
        config1 = self.create_sip_config(name='Config1', is_default=True, created_by=admin)
        config2 = self.create_sip_config(
            name='Config2', is_default=True, created_by=admin,
            username='user2', sip_server='sip2.test.com',
        )
        config1.refresh_from_db()
        self.assertFalse(config1.is_default)
        self.assertTrue(config2.is_default)

    def test_setting_non_default_does_not_clear_others(self):
        admin = self.create_admin()
        config1 = self.create_sip_config(name='C1', is_default=True, created_by=admin)
        config2 = self.create_sip_config(
            name='C2', is_default=False, created_by=admin,
            username='u2', sip_server='s2.test.com',
        )
        config1.refresh_from_db()
        self.assertTrue(config1.is_default)
        self.assertFalse(config2.is_default)

    def test_ordering(self):
        admin = self.create_admin()
        c1 = self.create_sip_config(name='B Config', created_by=admin, is_default=False)
        c2 = self.create_sip_config(
            name='A Config', created_by=admin, is_default=True,
            username='u2', sip_server='s2.test.com',
        )
        configs = list(SipConfiguration.objects.all())
        self.assertEqual(configs[0].id, c2.id)  # default first


# ============================================================================
# UserPhoneAssignment
# ============================================================================


class TestUserPhoneAssignment(CrmTestCase):

    def test_creation(self):
        admin = self.create_admin()
        sip_config = self.create_sip_config(created_by=admin)
        user = self.create_user(email='agent1@test.com')
        assignment = self.create_phone_assignment(
            user=user, sip_config=sip_config, extension='100',
        )
        self.assertEqual(assignment.extension, '100')
        self.assertTrue(assignment.is_primary)

    def test_str_representation(self):
        assignment = self.create_phone_assignment()
        self.assertIn('ext', str(assignment))

    def test_is_primary_uniqueness_per_user(self):
        """Only one primary assignment per user."""
        user = self.create_user(email='multi@test.com')
        sip_config = self.create_sip_config()
        a1 = self.create_phone_assignment(
            user=user, sip_config=sip_config,
            extension='100', is_primary=True,
        )
        sip_config2 = self.create_sip_config(
            name='SIP2', sip_server='sip2.test.com', username='u2',
        )
        a2 = self.create_phone_assignment(
            user=user, sip_config=sip_config2,
            extension='101', is_primary=True,
        )
        a1.refresh_from_db()
        self.assertFalse(a1.is_primary)
        self.assertTrue(a2.is_primary)

    def test_extension_unique_per_sip_config(self):
        """Each extension must be unique within a SIP configuration."""
        sip_config = self.create_sip_config()
        user1 = self.create_user(email='u1@test.com')
        user2 = self.create_user(email='u2@test.com')
        self.create_phone_assignment(
            user=user1, sip_config=sip_config, extension='100',
        )
        with self.assertRaises(IntegrityError):
            self.create_phone_assignment(
                user=user2, sip_config=sip_config, extension='100',
            )


# ============================================================================
# Client
# ============================================================================


class TestClient(CrmTestCase):

    def test_creation(self):
        client = self.create_client(name='Acme Corp')
        self.assertEqual(client.name, 'Acme Corp')
        self.assertTrue(client.is_active)

    def test_str_representation(self):
        client = self.create_client(name='Acme', email='acme@test.com')
        self.assertEqual(str(client), 'Acme (acme@test.com)')


# ============================================================================
# CallLog
# ============================================================================


class TestCallLog(CrmTestCase):

    def test_creation(self):
        call = self.create_call_log()
        self.assertEqual(call.status, 'ringing')
        self.assertEqual(call.direction, 'inbound')
        self.assertIsNotNone(call.call_id)

    def test_str_representation_inbound(self):
        call = self.create_call_log(direction='inbound')
        # Inbound uses left arrow
        self.assertIn('\u2190', str(call))

    def test_str_representation_outbound(self):
        call = self.create_call_log(direction='outbound')
        # Outbound uses right arrow
        self.assertIn('\u2192', str(call))

    def test_client_auto_matching_by_phone_last_7_digits(self):
        """CallLog.save() should auto-match a CRM Client by last 7 digits."""
        client = self.create_client(phone='+995555123456')
        call = self.create_call_log(
            caller_number='+995555123456',
            direction='inbound',
        )
        self.assertEqual(call.client, client)

    def test_client_auto_matching_outbound(self):
        """For outbound calls, the recipient number is matched."""
        client = self.create_client(phone='0555222333')
        call = self.create_call_log(
            recipient_number='+995555222333',
            direction='outbound',
        )
        self.assertEqual(call.client, client)

    def test_client_auto_matching_no_match(self):
        """If no client matches, client should remain None."""
        call = self.create_call_log(caller_number='+999999999999')
        self.assertIsNone(call.client)

    def test_status_choices(self):
        valid_statuses = [c[0] for c in CallLog.STATUS_CHOICES]
        for s in ['initiated', 'ringing', 'answered', 'missed', 'ended']:
            self.assertIn(s, valid_statuses)

    def test_duration_field(self):
        now = timezone.now()
        call = self.create_call_log(
            answered_at=now - timedelta(minutes=5),
            ended_at=now,
            duration=timedelta(minutes=5),
            status='ended',
        )
        self.assertEqual(call.duration.total_seconds(), 300)


# ============================================================================
# CallEvent
# ============================================================================


class TestCallEvent(CrmTestCase):

    def test_creation(self):
        call = self.create_call_log()
        event = self.create_call_event(call, event_type='initiated')
        self.assertEqual(event.event_type, 'initiated')
        self.assertEqual(event.call_log, call)

    def test_str_representation(self):
        call = self.create_call_log()
        event = self.create_call_event(call, event_type='answered')
        self.assertIn('answered', str(event))

    def test_event_types(self):
        valid_types = [c[0] for c in CallEvent.EVENT_TYPES]
        for t in ['initiated', 'ringing', 'answered', 'hold', 'ended', 'failed']:
            self.assertIn(t, valid_types)

    def test_metadata_default(self):
        call = self.create_call_log()
        event = self.create_call_event(call)
        self.assertEqual(event.metadata, {})

    def test_metadata_with_data(self):
        call = self.create_call_log()
        event = self.create_call_event(
            call, metadata={'sip_config': 'test', 'key': 'value'}
        )
        self.assertEqual(event.metadata['sip_config'], 'test')


# ============================================================================
# CallRecording
# ============================================================================


class TestCallRecording(CrmTestCase):

    def test_creation(self):
        call = self.create_call_log()
        recording = self.create_call_recording(call)
        self.assertEqual(recording.status, 'pending')
        self.assertIsNotNone(recording.recording_id)

    def test_str_representation(self):
        call = self.create_call_log()
        recording = self.create_call_recording(call, status='completed')
        self.assertIn('completed', str(recording))
        self.assertIn(str(call.call_id), str(recording))

    def test_status_transitions(self):
        call = self.create_call_log()
        recording = self.create_call_recording(call, status='pending')
        for new_status in ['recording', 'processing', 'completed']:
            recording.status = new_status
            recording.save()
            recording.refresh_from_db()
            self.assertEqual(recording.status, new_status)

    def test_one_to_one_constraint(self):
        """Only one recording per call log."""
        call = self.create_call_log()
        self.create_call_recording(call)
        with self.assertRaises(IntegrityError):
            self.create_call_recording(call)


# ============================================================================
# PbxSettings
# ============================================================================


class TestPbxSettings(CrmTestCase):

    def test_creation(self):
        sip_config = self.create_sip_config()
        settings = self.create_pbx_settings(sip_config=sip_config)
        self.assertEqual(settings.sip_configuration, sip_config)
        self.assertFalse(settings.working_hours_enabled)

    def test_str_representation(self):
        sip_config = self.create_sip_config(name='Office PBX')
        settings = self.create_pbx_settings(sip_config=sip_config)
        self.assertEqual(str(settings), 'PBX Settings for Office PBX')

    def test_is_working_hours_now_disabled(self):
        """When working_hours_enabled is False, always returns True."""
        settings = self.create_pbx_settings(working_hours_enabled=False)
        self.assertTrue(settings.is_working_hours_now())

    def test_is_working_hours_now_empty_schedule(self):
        """When schedule is empty, always returns True."""
        settings = self.create_pbx_settings(
            working_hours_enabled=True,
            working_hours_schedule={},
        )
        self.assertTrue(settings.is_working_hours_now())

    @patch('crm.models.timezone.now')
    def test_is_working_hours_now_within_hours(self, mock_now):
        """Should return True when current time is within schedule."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        # Mock time to Wednesday 10:00 Tbilisi time
        tz = ZoneInfo('Asia/Tbilisi')
        mock_now.return_value = datetime(2026, 4, 8, 6, 0, 0, tzinfo=ZoneInfo('UTC'))
        # 06:00 UTC = 10:00 Asia/Tbilisi
        settings = self.create_pbx_settings(
            working_hours_enabled=True,
            working_hours_schedule={
                'wednesday': [9, 10, 11, 12, 13, 14, 15, 16, 17],
            },
            timezone='Asia/Tbilisi',
        )
        self.assertTrue(settings.is_working_hours_now())

    @patch('crm.models.timezone.now')
    def test_is_working_hours_now_outside_hours(self, mock_now):
        """Should return False when current time is outside schedule."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        # Mock time to Wednesday 02:00 Tbilisi time
        mock_now.return_value = datetime(2026, 4, 7, 22, 0, 0, tzinfo=ZoneInfo('UTC'))
        # 22:00 UTC = 02:00+1 Asia/Tbilisi → actually Wednesday early morning
        settings = self.create_pbx_settings(
            working_hours_enabled=True,
            working_hours_schedule={
                'wednesday': [9, 10, 11, 12, 13, 14, 15, 16, 17],
            },
            timezone='Asia/Tbilisi',
        )
        self.assertFalse(settings.is_working_hours_now())

    @patch('crm.models.timezone.now')
    def test_is_working_hours_now_holiday_overrides(self, mock_now):
        """Holiday dates should override working hours as closed."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        # Mock time to Wednesday 10:00 Tbilisi = normally open
        mock_now.return_value = datetime(2026, 4, 8, 6, 0, 0, tzinfo=ZoneInfo('UTC'))
        settings = self.create_pbx_settings(
            working_hours_enabled=True,
            working_hours_schedule={
                'wednesday': [9, 10, 11, 12, 13, 14, 15, 16, 17],
            },
            timezone='Asia/Tbilisi',
            holidays=[{'date': '2026-04-08', 'name': 'Test Holiday'}],
        )
        self.assertFalse(settings.is_working_hours_now())

    @patch('crm.models.timezone.now')
    def test_is_working_hours_day_not_in_schedule(self, mock_now):
        """Should return False for a day not listed in schedule."""
        from datetime import datetime
        from zoneinfo import ZoneInfo
        # Mock time to Saturday 10:00 Tbilisi
        mock_now.return_value = datetime(2026, 4, 11, 6, 0, 0, tzinfo=ZoneInfo('UTC'))
        settings = self.create_pbx_settings(
            working_hours_enabled=True,
            working_hours_schedule={
                'monday': [9, 10, 11, 12, 13, 14, 15, 16, 17],
                'tuesday': [9, 10, 11, 12, 13, 14, 15, 16, 17],
            },
            timezone='Asia/Tbilisi',
        )
        self.assertFalse(settings.is_working_hours_now())

    def test_get_sound_urls_empty(self):
        """Should return dict with None values when no sounds uploaded."""
        settings = self.create_pbx_settings()
        urls = settings.get_sound_urls()
        self.assertIsInstance(urls, dict)
        self.assertIn('greeting', urls)
        self.assertIn('after_hours', urls)
        self.assertIsNone(urls['greeting'])
        self.assertIsNone(urls['after_hours'])

    def test_one_to_one_constraint(self):
        """Only one PbxSettings per SipConfiguration."""
        sip_config = self.create_sip_config()
        self.create_pbx_settings(sip_config=sip_config)
        with self.assertRaises(IntegrityError):
            PbxSettings.objects.create(sip_configuration=sip_config)
