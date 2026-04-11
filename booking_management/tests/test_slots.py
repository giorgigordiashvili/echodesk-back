"""
Tests for slot generation logic in booking_management.utils.
Covers fixed_slots and duration_based booking types, break exclusion,
double-booking prevention, staff availability, and multi-staff grouping.
"""
from decimal import Decimal
from datetime import date, time, timedelta

from booking_management.tests.conftest import BookingTestCase
from booking_management.utils import generate_available_slots


class FixedSlotTests(BookingTestCase):
    """Tests for generate_available_slots with booking_type='fixed_slots'."""

    def setUp(self):
        super().setUp()
        self.staff = self.create_staff()
        # Staff works Mon (day 0) from 09:00-17:00
        self.create_availability(self.staff, day_of_week=0)
        self.service = self.create_service(
            booking_type='fixed_slots',
            available_time_slots=['09:00', '10:00', '11:00', '14:00', '16:00'],
            duration_minutes=60,
            buffer_time_minutes=0,
        )
        self.service.staff_members.add(self.staff)
        # Find the next Monday from today
        today = date.today()
        days_ahead = 0 - today.weekday()  # Monday = 0
        if days_ahead <= 0:
            days_ahead += 7
        self.next_monday = today + timedelta(days=days_ahead)

    def test_fixed_slots_returns_predefined_times(self):
        """All predefined time slots within working hours are returned."""
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        self.assertIn('09:00', start_times)
        self.assertIn('10:00', start_times)
        self.assertIn('11:00', start_times)
        self.assertIn('14:00', start_times)
        self.assertIn('16:00', start_times)
        self.assertEqual(len(slots), 5)

    def test_fixed_slots_excludes_booked_slot(self):
        """A slot with an existing booking is excluded."""
        client = self.create_client()
        self.create_booking(
            self.service,
            client=client,
            staff=self.staff,
            date=self.next_monday,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status='confirmed',
        )
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        self.assertNotIn('10:00', start_times)
        # Other slots should still be present
        self.assertIn('09:00', start_times)
        self.assertIn('11:00', start_times)

    def test_fixed_slots_excludes_break_time(self):
        """Slots falling in break time are excluded."""
        # Update availability to have a break 12:00-13:00
        avail = self.staff.availability.first()
        avail.break_start = time(13, 30)
        avail.break_end = time(15, 0)
        avail.save()

        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        # 14:00 falls within break (13:30-15:00), so should be excluded
        self.assertNotIn('14:00', start_times)
        # Others should remain
        self.assertIn('09:00', start_times)
        self.assertIn('10:00', start_times)

    def test_fixed_slots_without_staff_checks_all(self):
        """When staff is None, all active staff are checked."""
        staff2 = self.create_staff()
        self.create_availability(staff2, day_of_week=0)
        self.service.staff_members.add(staff2)

        slots = generate_available_slots(self.service, self.next_monday)
        # With grouping, each time slot appears once but with multiple staff in available_staff
        start_times = [s['start_time'] for s in slots]
        self.assertEqual(len(set(start_times)), 5)
        # At least one slot should have 2 available staff
        multi_staff_slot = [s for s in slots if len(s['available_staff']) == 2]
        self.assertTrue(len(multi_staff_slot) > 0)

    def test_fixed_slots_empty_when_no_availability(self):
        """No slots when staff has no availability for that day."""
        # Next Tuesday (day 1) -- staff only has Monday availability
        next_tuesday = self.next_monday + timedelta(days=1)
        slots = generate_available_slots(self.service, next_tuesday, staff=self.staff)
        self.assertEqual(slots, [])


class DurationBasedSlotTests(BookingTestCase):
    """Tests for generate_available_slots with booking_type='duration_based'."""

    def setUp(self):
        super().setUp()
        self.staff = self.create_staff()
        # Staff works Mon (day 0) from 09:00-12:00 (short window for predictable counts)
        self.create_availability(
            self.staff,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(12, 0),
        )
        self.service = self.create_service(
            booking_type='duration_based',
            duration_minutes=30,
            buffer_time_minutes=0,
            base_price=Decimal('40.00'),
        )
        self.service.staff_members.add(self.staff)
        # Find the next Monday
        today = date.today()
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        self.next_monday = today + timedelta(days=days_ahead)

    def test_duration_based_generates_slots_at_intervals(self):
        """Slots are generated at 30-min intervals within working hours."""
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        # 09:00-12:00, 30-min service, 0 buffer => slots at 09:00, 09:30, 10:00, 10:30, 11:00, 11:30
        expected = ['09:00', '09:30', '10:00', '10:30', '11:00', '11:30']
        self.assertEqual(start_times, expected)

    def test_duration_based_respects_buffer(self):
        """Buffer time reduces available slots (service + buffer must fit)."""
        service = self.create_service(
            booking_type='duration_based',
            duration_minutes=30,
            buffer_time_minutes=30,
        )
        service.staff_members.add(self.staff)
        # total_duration = 60 min; working 09:00-12:00
        # Slots: 09:00 (end 10:00), 09:30 (end 10:30), 10:00 (end 11:00), 10:30 (end 11:30), 11:00 (end 12:00)
        # 11:30 won't fit because 11:30 + 60 = 12:30 > 12:00
        slots = generate_available_slots(service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        self.assertEqual(start_times, ['09:00', '09:30', '10:00', '10:30', '11:00'])

    def test_duration_based_end_time_shows_service_duration_only(self):
        """Displayed end_time uses service duration, not total (service+buffer)."""
        service = self.create_service(
            booking_type='duration_based',
            duration_minutes=30,
            buffer_time_minutes=30,
        )
        service.staff_members.add(self.staff)
        slots = generate_available_slots(service, self.next_monday, staff=self.staff)
        # First slot starts at 09:00, display end = 09:00 + 30min = 09:30
        first = slots[0]
        self.assertEqual(first['start_time'], '09:00')
        # end_time in grouped result uses first slot's end_time
        self.assertEqual(first['end_time'], '09:30')

    def test_duration_based_excludes_existing_booking(self):
        """A slot overlapping with an existing booking is excluded."""
        client = self.create_client()
        self.create_booking(
            self.service,
            client=client,
            staff=self.staff,
            date=self.next_monday,
            start_time=time(10, 0),
            end_time=time(10, 30),
            status='confirmed',
        )
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        self.assertNotIn('10:00', start_times)
        # Adjacent slots should still be present
        self.assertIn('09:00', start_times)
        self.assertIn('10:30', start_times)

    def test_duration_based_excludes_break_time(self):
        """Slots during break time are excluded."""
        avail = self.staff.availability.first()
        avail.break_start = time(10, 0)
        avail.break_end = time(10, 30)
        avail.save()

        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        # 10:00 is in break range [10:00, 10:30), should be excluded
        self.assertNotIn('10:00', start_times)
        # 09:30 is before break start, should be present
        self.assertIn('09:30', start_times)
        # 10:30 is at break_end so should be present (is_time_in_range uses < for end)
        self.assertIn('10:30', start_times)

    def test_duration_based_small_service_short_interval(self):
        """When service duration < 30min, interval = service duration."""
        service = self.create_service(
            booking_type='duration_based',
            duration_minutes=15,
            buffer_time_minutes=0,
        )
        service.staff_members.add(self.staff)
        slots = generate_available_slots(service, self.next_monday, staff=self.staff)
        # interval = min(30, 15) = 15 min. 09:00-12:00, 15-min service
        # slots at 09:00, 09:15, 09:30, ... 11:45 => (12*60 - 9*60)/15 = 12 slots
        start_times = [s['start_time'] for s in slots]
        self.assertEqual(len(start_times), 12)
        self.assertEqual(start_times[0], '09:00')
        self.assertEqual(start_times[-1], '11:45')


class NoAvailabilityTests(BookingTestCase):
    """Tests for edge cases where no slots should be generated."""

    def setUp(self):
        super().setUp()
        self.staff = self.create_staff()
        self.service = self.create_service(booking_type='duration_based')
        self.service.staff_members.add(self.staff)
        # Find next Monday
        today = date.today()
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        self.next_monday = today + timedelta(days=days_ahead)

    def test_empty_slots_when_no_availability_record(self):
        """No availability record for the day returns empty list."""
        # Staff has no availability records at all
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        self.assertEqual(slots, [])

    def test_empty_slots_when_availability_is_unavailable(self):
        """Availability record with is_available=False returns empty."""
        self.create_availability(
            self.staff,
            day_of_week=0,
            is_available=False,
        )
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        self.assertEqual(slots, [])

    def test_empty_slots_on_day_off(self):
        """Staff has Mon availability but checking Tuesday returns empty."""
        self.create_availability(self.staff, day_of_week=0)  # Monday only
        next_tuesday = self.next_monday + timedelta(days=1)
        slots = generate_available_slots(self.service, next_tuesday, staff=self.staff)
        self.assertEqual(slots, [])

    def test_empty_slots_with_staff_exception_unavailable(self):
        """StaffException marking day unavailable overrides regular schedule."""
        self.create_availability(self.staff, day_of_week=0)
        self.create_staff_exception(
            self.staff,
            exception_date=self.next_monday,
            is_available=False,
        )
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        self.assertEqual(slots, [])

    def test_staff_exception_with_custom_hours(self):
        """StaffException with is_available=True and custom hours is respected."""
        self.create_availability(self.staff, day_of_week=0, start_time=time(9, 0), end_time=time(17, 0))
        # Exception: available but only 10:00-11:00
        self.create_staff_exception(
            self.staff,
            exception_date=self.next_monday,
            is_available=True,
            start_time=time(10, 0),
            end_time=time(11, 0),
        )
        service = self.create_service(
            booking_type='duration_based',
            duration_minutes=30,
            buffer_time_minutes=0,
        )
        service.staff_members.add(self.staff)
        slots = generate_available_slots(service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        # Only 10:00-11:00 window, 30-min service => 10:00 and 10:30
        self.assertEqual(start_times, ['10:00', '10:30'])

    def test_inactive_staff_excluded_from_no_staff_query(self):
        """Staff with is_active_for_bookings=False is not included."""
        self.create_availability(self.staff, day_of_week=0)
        self.staff.is_active_for_bookings = False
        self.staff.save()
        # No specific staff -- function checks service.staff_members.filter(is_active_for_bookings=True)
        slots = generate_available_slots(self.service, self.next_monday, staff=None)
        self.assertEqual(slots, [])


class MultiStaffSlotTests(BookingTestCase):
    """Tests for multiple staff at same time (grouped, not deduplicated)."""

    def setUp(self):
        super().setUp()
        self.staff1 = self.create_staff()
        self.staff2 = self.create_staff()
        # Both staff work Mon 09:00-12:00
        self.create_availability(self.staff1, day_of_week=0, start_time=time(9, 0), end_time=time(12, 0))
        self.create_availability(self.staff2, day_of_week=0, start_time=time(9, 0), end_time=time(12, 0))
        self.service = self.create_service(
            booking_type='duration_based',
            duration_minutes=30,
            buffer_time_minutes=0,
        )
        self.service.staff_members.add(self.staff1, self.staff2)
        # Find next Monday
        today = date.today()
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        self.next_monday = today + timedelta(days=days_ahead)

    def test_multi_staff_grouped_by_time(self):
        """When no staff specified, slots are grouped by time with available_staff list."""
        slots = generate_available_slots(self.service, self.next_monday)
        # Each time slot should appear once (grouped)
        start_times = [s['start_time'] for s in slots]
        self.assertEqual(len(start_times), len(set(start_times)), "Slot times should be unique after grouping")

    def test_multi_staff_available_staff_count(self):
        """Each grouped slot shows both staff in available_staff."""
        slots = generate_available_slots(self.service, self.next_monday)
        # All slots should have 2 available staff
        for slot in slots:
            self.assertEqual(
                len(slot['available_staff']),
                2,
                f"Slot {slot['start_time']} should have 2 available staff",
            )

    def test_multi_staff_one_booked_still_shows_slot(self):
        """When one staff is booked, the slot still appears for the other staff."""
        client = self.create_client()
        self.create_booking(
            self.service,
            client=client,
            staff=self.staff1,
            date=self.next_monday,
            start_time=time(10, 0),
            end_time=time(10, 30),
            status='confirmed',
        )
        slots = generate_available_slots(self.service, self.next_monday)
        slot_10 = [s for s in slots if s['start_time'] == '10:00']
        self.assertEqual(len(slot_10), 1, "10:00 slot should still appear")
        # Only staff2 should be available at 10:00
        self.assertEqual(len(slot_10[0]['available_staff']), 1)
        self.assertEqual(slot_10[0]['available_staff'][0]['staff_id'], self.staff2.id)

    def test_multi_staff_both_booked_removes_slot(self):
        """When both staff are booked at same time, that slot disappears."""
        client = self.create_client()
        for staff_member in [self.staff1, self.staff2]:
            self.create_booking(
                self.service,
                client=client,
                staff=staff_member,
                date=self.next_monday,
                start_time=time(10, 0),
                end_time=time(10, 30),
                status='confirmed',
            )
        slots = generate_available_slots(self.service, self.next_monday)
        start_times = [s['start_time'] for s in slots]
        self.assertNotIn('10:00', start_times)

    def test_multi_staff_different_availability(self):
        """Staff with different hours produce correct grouped output."""
        # Override: staff2 works 10:00-12:00 instead of 09:00-12:00
        avail2 = self.staff2.availability.first()
        avail2.start_time = time(10, 0)
        avail2.save()

        slots = generate_available_slots(self.service, self.next_monday)

        # 09:00 and 09:30 should only have staff1
        slot_0900 = [s for s in slots if s['start_time'] == '09:00']
        self.assertEqual(len(slot_0900), 1)
        self.assertEqual(len(slot_0900[0]['available_staff']), 1)
        self.assertEqual(slot_0900[0]['available_staff'][0]['staff_id'], self.staff1.id)

        # 10:00 should have both
        slot_1000 = [s for s in slots if s['start_time'] == '10:00']
        self.assertEqual(len(slot_1000), 1)
        self.assertEqual(len(slot_1000[0]['available_staff']), 2)


class DoubleBookingPreventionTests(BookingTestCase):
    """Tests ensuring existing bookings prevent overlapping slots."""

    def setUp(self):
        super().setUp()
        self.staff = self.create_staff()
        self.create_availability(
            self.staff,
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(13, 0),
        )
        self.service = self.create_service(
            booking_type='duration_based',
            duration_minutes=60,
            buffer_time_minutes=0,
        )
        self.service.staff_members.add(self.staff)
        # Find next Monday
        today = date.today()
        days_ahead = 0 - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        self.next_monday = today + timedelta(days=days_ahead)

    def test_pending_booking_blocks_slot(self):
        """Pending booking blocks overlapping slots."""
        client = self.create_client()
        self.create_booking(
            self.service,
            client=client,
            staff=self.staff,
            date=self.next_monday,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status='pending',
        )
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        self.assertNotIn('10:00', start_times)

    def test_confirmed_booking_blocks_slot(self):
        """Confirmed booking blocks overlapping slots."""
        client = self.create_client()
        self.create_booking(
            self.service,
            client=client,
            staff=self.staff,
            date=self.next_monday,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status='confirmed',
        )
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        self.assertNotIn('10:00', start_times)

    def test_in_progress_booking_blocks_slot(self):
        """In-progress booking blocks overlapping slots."""
        client = self.create_client()
        self.create_booking(
            self.service,
            client=client,
            staff=self.staff,
            date=self.next_monday,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status='in_progress',
        )
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        self.assertNotIn('10:00', start_times)

    def test_cancelled_booking_does_not_block_slot(self):
        """Cancelled booking does NOT block the slot."""
        client = self.create_client()
        self.create_booking(
            self.service,
            client=client,
            staff=self.staff,
            date=self.next_monday,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status='cancelled',
        )
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        self.assertIn('10:00', start_times)

    def test_completed_booking_does_not_block_slot(self):
        """Completed booking does NOT block the slot."""
        client = self.create_client()
        self.create_booking(
            self.service,
            client=client,
            staff=self.staff,
            date=self.next_monday,
            start_time=time(10, 0),
            end_time=time(11, 0),
            status='completed',
        )
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        self.assertIn('10:00', start_times)

    def test_adjacent_bookings_leave_gap(self):
        """Back-to-back bookings leave no gap between them."""
        client = self.create_client()
        # Book 09:00-10:00 and 11:00-12:00, leaving 10:00-11:00 open
        self.create_booking(
            self.service, client=client, staff=self.staff,
            date=self.next_monday, start_time=time(9, 0), end_time=time(10, 0),
            status='confirmed',
        )
        self.create_booking(
            self.service, client=client, staff=self.staff,
            date=self.next_monday, start_time=time(11, 0), end_time=time(12, 0),
            status='confirmed',
        )
        slots = generate_available_slots(self.service, self.next_monday, staff=self.staff)
        start_times = [s['start_time'] for s in slots]
        self.assertNotIn('09:00', start_times)
        self.assertIn('10:00', start_times)
        self.assertNotIn('11:00', start_times)
        self.assertIn('12:00', start_times)
