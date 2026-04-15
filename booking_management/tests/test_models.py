"""
Tests for booking management model logic.
Covers Service calculations, Booking status transitions,
RecurringBooking scheduling, and BookingSettings defaults.
"""
from decimal import Decimal
from datetime import date, time, timedelta

from django.utils import timezone

from booking_management.tests.conftest import BookingTestCase
from booking_management.models import BookingSettings


class ServiceCalculationTests(BookingTestCase):
    """Tests for Service.total_duration_minutes and deposit calculations."""

    def test_total_duration_minutes_with_buffer(self):
        """total_duration_minutes = duration + buffer."""
        service = self.create_service(duration_minutes=60, buffer_time_minutes=10)
        self.assertEqual(service.total_duration_minutes, 70)

    def test_total_duration_minutes_zero_buffer(self):
        """Zero buffer means total equals duration."""
        service = self.create_service(duration_minutes=45, buffer_time_minutes=0)
        self.assertEqual(service.total_duration_minutes, 45)

    def test_total_duration_minutes_large_buffer(self):
        """Large buffer is accumulated correctly."""
        service = self.create_service(duration_minutes=30, buffer_time_minutes=30)
        self.assertEqual(service.total_duration_minutes, 60)

    def test_deposit_amount_calculation(self):
        """Deposit = base_price * deposit_percentage / 100."""
        service = self.create_service(base_price=Decimal('100.00'), deposit_percentage=20)
        self.assertEqual(service.calculate_deposit_amount(), Decimal('20.00'))

    def test_deposit_amount_zero_percentage(self):
        """Zero deposit percentage gives zero deposit."""
        service = self.create_service(base_price=Decimal('100.00'), deposit_percentage=0)
        self.assertEqual(service.calculate_deposit_amount(), Decimal('0.00'))

    def test_deposit_amount_full_percentage(self):
        """100% deposit equals base price."""
        service = self.create_service(base_price=Decimal('80.00'), deposit_percentage=100)
        self.assertEqual(service.calculate_deposit_amount(), Decimal('80.00'))

    def test_remaining_amount_after_deposit(self):
        """Remaining = base_price - deposit."""
        service = self.create_service(base_price=Decimal('200.00'), deposit_percentage=25)
        self.assertEqual(service.calculate_remaining_amount(), Decimal('150.00'))

    def test_remaining_amount_no_deposit(self):
        """With 0% deposit, remaining equals full base price."""
        service = self.create_service(base_price=Decimal('75.50'), deposit_percentage=0)
        self.assertEqual(service.calculate_remaining_amount(), Decimal('75.50'))

    def test_deposit_amount_fractional(self):
        """Deposit calculation with fractional result."""
        service = self.create_service(base_price=Decimal('99.99'), deposit_percentage=33)
        expected = (Decimal('99.99') * Decimal('33')) / Decimal('100')
        self.assertEqual(service.calculate_deposit_amount(), expected)


class BookingStatusTransitionTests(BookingTestCase):
    """Tests for Booking status lifecycle methods."""

    def setUp(self):
        super().setUp()
        self.service = self.create_service()
        self.staff = self.create_staff()

    def test_initial_status_is_pending(self):
        """New booking starts with pending status."""
        booking = self.create_booking(self.service, staff=self.staff)
        self.assertEqual(booking.status, 'pending')

    def test_confirm_sets_status_and_timestamp(self):
        """confirm() transitions to confirmed and sets confirmed_at."""
        booking = self.create_booking(self.service, staff=self.staff)
        self.assertIsNone(booking.confirmed_at)
        booking.confirm()
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'confirmed')
        self.assertIsNotNone(booking.confirmed_at)

    def test_complete_sets_status_and_timestamp(self):
        """complete() transitions to completed and sets completed_at."""
        booking = self.create_booking(self.service, staff=self.staff)
        booking.confirm()
        booking.complete()
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'completed')
        self.assertIsNotNone(booking.completed_at)

    def test_cancel_sets_all_cancellation_fields(self):
        """cancel() sets status, cancelled_at, cancelled_by, and reason."""
        booking = self.create_booking(self.service, staff=self.staff)
        booking.cancel(cancelled_by='client', reason='Changed my mind')
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')
        self.assertIsNotNone(booking.cancelled_at)
        self.assertEqual(booking.cancelled_by, 'client')
        self.assertEqual(booking.cancellation_reason, 'Changed my mind')

    def test_cancel_by_staff(self):
        """Staff cancellation is recorded correctly."""
        booking = self.create_booking(self.service, staff=self.staff)
        booking.confirm()
        booking.cancel(cancelled_by='staff', reason='Staff unavailable')
        booking.refresh_from_db()
        self.assertEqual(booking.cancelled_by, 'staff')

    def test_cancel_by_admin(self):
        """Admin cancellation is recorded correctly."""
        booking = self.create_booking(self.service, staff=self.staff)
        booking.cancel(cancelled_by='admin', reason='Policy violation')
        booking.refresh_from_db()
        self.assertEqual(booking.cancelled_by, 'admin')

    def test_pending_to_confirmed_to_completed(self):
        """Full happy-path lifecycle: pending -> confirmed -> completed."""
        booking = self.create_booking(self.service, staff=self.staff)
        self.assertEqual(booking.status, 'pending')

        booking.confirm()
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'confirmed')

        booking.complete()
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'completed')

    def test_pending_to_cancelled(self):
        """Booking can be cancelled directly from pending."""
        booking = self.create_booking(self.service, staff=self.staff)
        booking.cancel(cancelled_by='client', reason='No longer needed')
        booking.refresh_from_db()
        self.assertEqual(booking.status, 'cancelled')

    def test_is_paid_property(self):
        """is_paid returns True only when payment_status is fully_paid."""
        booking = self.create_booking(self.service, staff=self.staff)
        self.assertFalse(booking.is_paid)
        booking.payment_status = 'fully_paid'
        booking.save()
        booking.refresh_from_db()
        self.assertTrue(booking.is_paid)

    def test_remaining_amount_property(self):
        """remaining_amount = total_amount - paid_amount."""
        booking = self.create_booking(
            self.service,
            staff=self.staff,
            total_amount=Decimal('100.00'),
            paid_amount=Decimal('30.00'),
        )
        self.assertEqual(booking.remaining_amount, Decimal('70.00'))

    def test_remaining_amount_fully_paid(self):
        """remaining_amount is zero when fully paid."""
        booking = self.create_booking(
            self.service,
            staff=self.staff,
            total_amount=Decimal('100.00'),
            paid_amount=Decimal('100.00'),
        )
        self.assertEqual(booking.remaining_amount, Decimal('0.00'))

    def test_booking_number_auto_generated(self):
        """Booking number is auto-generated and starts with BK."""
        booking = self.create_booking(self.service, staff=self.staff)
        self.assertTrue(booking.booking_number.startswith('BK'))
        self.assertGreater(len(booking.booking_number), 10)


class RecurringBookingTests(BookingTestCase):
    """Tests for RecurringBooking scheduling logic."""

    def setUp(self):
        super().setUp()
        self.service = self.create_service()
        self.staff = self.create_staff()
        self.bk_client = self.create_client()

    def test_weekly_next_date(self):
        """Weekly frequency advances by 7 days."""
        rb = self.create_recurring_booking(
            self.service,
            client=self.bk_client,
            staff=self.staff,
            frequency='weekly',
            next_booking_date=date(2026, 4, 6),
        )
        next_date = rb.calculate_next_date()
        self.assertEqual(next_date, date(2026, 4, 13))

    def test_biweekly_next_date(self):
        """Biweekly frequency advances by 14 days."""
        rb = self.create_recurring_booking(
            self.service,
            client=self.bk_client,
            staff=self.staff,
            frequency='biweekly',
            next_booking_date=date(2026, 4, 6),
        )
        next_date = rb.calculate_next_date()
        self.assertEqual(next_date, date(2026, 4, 20))

    def test_monthly_next_date(self):
        """Monthly frequency advances by one month."""
        rb = self.create_recurring_booking(
            self.service,
            client=self.bk_client,
            staff=self.staff,
            frequency='monthly',
            next_booking_date=date(2026, 3, 15),
        )
        next_date = rb.calculate_next_date()
        self.assertEqual(next_date, date(2026, 4, 15))

    def test_monthly_handles_month_end_jan31_to_feb28(self):
        """Jan 31 -> Feb 28 (non-leap year)."""
        rb = self.create_recurring_booking(
            self.service,
            client=self.bk_client,
            staff=self.staff,
            frequency='monthly',
            next_booking_date=date(2027, 1, 31),
        )
        next_date = rb.calculate_next_date()
        self.assertEqual(next_date, date(2027, 2, 28))

    def test_monthly_handles_month_end_jan31_to_feb29_leap(self):
        """Jan 31 -> Feb 29 in a leap year (2028)."""
        rb = self.create_recurring_booking(
            self.service,
            client=self.bk_client,
            staff=self.staff,
            frequency='monthly',
            next_booking_date=date(2028, 1, 31),
        )
        next_date = rb.calculate_next_date()
        self.assertEqual(next_date, date(2028, 2, 29))

    def test_monthly_handles_march31_to_april30(self):
        """Mar 31 -> Apr 30 (30-day month clamping)."""
        rb = self.create_recurring_booking(
            self.service,
            client=self.bk_client,
            staff=self.staff,
            frequency='monthly',
            next_booking_date=date(2026, 3, 31),
        )
        next_date = rb.calculate_next_date()
        self.assertEqual(next_date, date(2026, 4, 30))

    def test_monthly_december_to_january_year_wrap(self):
        """Dec -> Jan wraps to next year."""
        rb = self.create_recurring_booking(
            self.service,
            client=self.bk_client,
            staff=self.staff,
            frequency='monthly',
            next_booking_date=date(2026, 12, 15),
        )
        next_date = rb.calculate_next_date()
        self.assertEqual(next_date, date(2027, 1, 15))

    def test_should_create_booking_active_and_date_reached(self):
        """should_create_booking True when active and date is reached."""
        rb = self.create_recurring_booking(
            self.service,
            client=self.bk_client,
            staff=self.staff,
            next_booking_date=date.today(),
        )
        self.assertTrue(rb.should_create_booking())

    def test_should_create_booking_false_when_paused(self):
        """should_create_booking False when status is paused."""
        rb = self.create_recurring_booking(
            self.service,
            client=self.bk_client,
            staff=self.staff,
            status='paused',
            next_booking_date=date.today(),
        )
        self.assertFalse(rb.should_create_booking())

    def test_should_create_booking_false_when_max_reached(self):
        """should_create_booking False when max_occurrences is reached."""
        rb = self.create_recurring_booking(
            self.service,
            client=self.bk_client,
            staff=self.staff,
            max_occurrences=5,
            current_occurrences=5,
            next_booking_date=date.today(),
        )
        self.assertFalse(rb.should_create_booking())

    def test_should_create_booking_false_when_end_date_passed(self):
        """should_create_booking False after end_date."""
        rb = self.create_recurring_booking(
            self.service,
            client=self.bk_client,
            staff=self.staff,
            end_date=date.today() - timedelta(days=1),
            next_booking_date=date.today(),
        )
        self.assertFalse(rb.should_create_booking())

    def test_should_create_booking_false_when_future_date(self):
        """should_create_booking False when next date is in the future."""
        rb = self.create_recurring_booking(
            self.service,
            client=self.bk_client,
            staff=self.staff,
            next_booking_date=date.today() + timedelta(days=30),
        )
        self.assertFalse(rb.should_create_booking())


class BookingSettingsTests(BookingTestCase):
    """Tests for BookingSettings defaults and field values."""

    def test_default_settings_values(self):
        """Verify defaults match expected business rules."""
        settings = self.create_settings()
        self.assertEqual(settings.payment_method, 'manual_transfer')
        self.assertFalse(settings.require_deposit)
        self.assertTrue(settings.allow_cash_payment)
        self.assertTrue(settings.allow_card_payment)
        self.assertEqual(settings.cancellation_hours_before, 24)
        self.assertEqual(settings.refund_policy, 'full')
        self.assertTrue(settings.auto_confirm_on_deposit)
        self.assertTrue(settings.auto_confirm_on_full_payment)
        self.assertEqual(settings.min_hours_before_booking, 2)
        self.assertEqual(settings.max_days_advance_booking, 60)

    def test_custom_settings_override_defaults(self):
        """Custom values override defaults properly."""
        settings = self.create_settings(
            cancellation_hours_before=48,
            refund_policy='no_refund',
            require_deposit=True,
            max_days_advance_booking=30,
        )
        self.assertEqual(settings.cancellation_hours_before, 48)
        self.assertEqual(settings.refund_policy, 'no_refund')
        self.assertTrue(settings.require_deposit)
        self.assertEqual(settings.max_days_advance_booking, 30)

    def test_bog_payment_method(self):
        """BOG gateway can be selected as payment method."""
        settings = self.create_settings(payment_method='bog_gateway')
        self.assertEqual(settings.payment_method, 'bog_gateway')

    def test_bank_transfer_details(self):
        """Bank transfer fields store correctly."""
        settings = self.create_settings(
            bank_name='TBC Bank',
            bank_iban='GE29TB0000000000000001',
            bank_account_holder='Test LLC',
        )
        self.assertEqual(settings.bank_name, 'TBC Bank')
        self.assertEqual(settings.bank_iban, 'GE29TB0000000000000001')
        self.assertEqual(settings.bank_account_holder, 'Test LLC')


class BookingStaffTests(BookingTestCase):
    """Tests for BookingStaff model logic."""

    def test_staff_str_uses_full_name(self):
        """__str__ returns the user full name."""
        user = self.create_user(
            email='named-staff@test.com',
            first_name='Jane',
            last_name='Doe',
        )
        staff = self.create_staff(user=user)
        self.assertIn('Jane', str(staff))
        self.assertIn('Doe', str(staff))
