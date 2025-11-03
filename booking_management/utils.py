from datetime import datetime, timedelta, time
from django.utils import timezone
from .models import Booking, StaffAvailability, StaffException


def generate_available_slots(service, date, staff=None, language='en'):
    """
    Generate list of available time slots for a service on a given date

    Args:
        service: Service instance
        date: Date to check availability
        staff: Optional BookingStaff instance
        language: Language for error messages

    Returns:
        list: List of available time slot dictionaries with start_time, end_time, staff_id
    """
    available_slots = []

    # Get day of week (0=Monday, 6=Sunday)
    day_of_week = date.weekday()

    # Handle fixed slots booking type
    if service.booking_type == 'fixed_slots' and service.available_time_slots:
        # Get predefined time slots
        time_slots = service.available_time_slots if isinstance(service.available_time_slots, list) else []

        # If specific staff requested
        if staff:
            staff_availability = get_staff_availability(staff, date)
            if not staff_availability:
                return []

            for slot_str in time_slots:
                try:
                    slot_time = datetime.strptime(slot_str, '%H:%M').time()
                    if is_time_in_range(slot_time, staff_availability['start_time'], staff_availability['end_time']):
                        # Check if not in break time
                        if not (staff_availability.get('break_start') and staff_availability.get('break_end') and
                                is_time_in_range(slot_time, staff_availability['break_start'], staff_availability['break_end'])):
                            # Check if slot is not already booked
                            if not is_slot_booked(staff, date, slot_time, service.total_duration_minutes):
                                end_time = add_minutes_to_time(slot_time, service.duration_minutes)
                                available_slots.append({
                                    'start_time': slot_time.strftime('%H:%M'),
                                    'end_time': end_time.strftime('%H:%M'),
                                    'staff_id': staff.id,
                                    'staff_name': str(staff)
                                })
                except ValueError:
                    continue

        # No specific staff - check all staff members
        else:
            for staff_member in service.staff_members.filter(is_active_for_bookings=True):
                staff_availability = get_staff_availability(staff_member, date)
                if not staff_availability:
                    continue

                for slot_str in time_slots:
                    try:
                        slot_time = datetime.strptime(slot_str, '%H:%M').time()
                        if is_time_in_range(slot_time, staff_availability['start_time'], staff_availability['end_time']):
                            if not (staff_availability.get('break_start') and staff_availability.get('break_end') and
                                    is_time_in_range(slot_time, staff_availability['break_start'], staff_availability['break_end'])):
                                if not is_slot_booked(staff_member, date, slot_time, service.total_duration_minutes):
                                    end_time = add_minutes_to_time(slot_time, service.duration_minutes)
                                    available_slots.append({
                                        'start_time': slot_time.strftime('%H:%M'),
                                        'end_time': end_time.strftime('%H:%M'),
                                        'staff_id': staff_member.id,
                                        'staff_name': str(staff_member)
                                    })
                    except ValueError:
                        continue

    # Handle duration-based booking type
    elif service.booking_type == 'duration_based':
        # Generate slots every 30 minutes (or service duration, whichever is smaller)
        slot_interval = min(30, service.duration_minutes)

        # If specific staff requested
        if staff:
            staff_availability = get_staff_availability(staff, date)
            if not staff_availability:
                return []

            current_time = staff_availability['start_time']
            end_time = staff_availability['end_time']

            while current_time < end_time:
                # Check if slot can fit before end time
                slot_end = add_minutes_to_time(current_time, service.total_duration_minutes)
                if time_to_minutes(slot_end) <= time_to_minutes(end_time):
                    # Check if not in break time
                    if not (staff_availability.get('break_start') and staff_availability.get('break_end') and
                            is_time_in_range(current_time, staff_availability['break_start'], staff_availability['break_end'])):
                        # Check if slot is not already booked
                        if not is_slot_booked(staff, date, current_time, service.total_duration_minutes):
                            slot_end_display = add_minutes_to_time(current_time, service.duration_minutes)
                            available_slots.append({
                                'start_time': current_time.strftime('%H:%M'),
                                'end_time': slot_end_display.strftime('%H:%M'),
                                'staff_id': staff.id,
                                'staff_name': str(staff)
                            })

                # Move to next slot
                current_time = add_minutes_to_time(current_time, slot_interval)

        # No specific staff - check all staff members
        else:
            for staff_member in service.staff_members.filter(is_active_for_bookings=True):
                staff_availability = get_staff_availability(staff_member, date)
                if not staff_availability:
                    continue

                current_time = staff_availability['start_time']
                end_time = staff_availability['end_time']

                while current_time < end_time:
                    slot_end = add_minutes_to_time(current_time, service.total_duration_minutes)
                    if time_to_minutes(slot_end) <= time_to_minutes(end_time):
                        if not (staff_availability.get('break_start') and staff_availability.get('break_end') and
                                is_time_in_range(current_time, staff_availability['break_start'], staff_availability['break_end'])):
                            if not is_slot_booked(staff_member, date, current_time, service.total_duration_minutes):
                                slot_end_display = add_minutes_to_time(current_time, service.duration_minutes)
                                available_slots.append({
                                    'start_time': current_time.strftime('%H:%M'),
                                    'end_time': slot_end_display.strftime('%H:%M'),
                                    'staff_id': staff_member.id,
                                    'staff_name': str(staff_member)
                                })

                    current_time = add_minutes_to_time(current_time, slot_interval)

    # Remove duplicates (same time with different staff)
    # For client view, group by time
    seen_times = set()
    unique_slots = []
    for slot in available_slots:
        time_key = slot['start_time']
        if time_key not in seen_times:
            seen_times.add(time_key)
            unique_slots.append(slot)

    return sorted(unique_slots, key=lambda x: x['start_time'])


def get_staff_availability(staff, date):
    """
    Get staff availability for a specific date

    Returns dict with start_time, end_time, break_start, break_end or None
    """
    day_of_week = date.weekday()

    # Check for exceptions first
    try:
        exception = StaffException.objects.get(staff=staff, date=date)
        if not exception.is_available:
            return None
        return {
            'start_time': exception.start_time or time(9, 0),
            'end_time': exception.end_time or time(17, 0),
            'break_start': None,
            'break_end': None
        }
    except StaffException.DoesNotExist:
        pass

    # Get regular availability
    try:
        availability = StaffAvailability.objects.get(staff=staff, day_of_week=day_of_week, is_available=True)
        return {
            'start_time': availability.start_time,
            'end_time': availability.end_time,
            'break_start': availability.break_start,
            'break_end': availability.break_end
        }
    except StaffAvailability.DoesNotExist:
        return None


def is_slot_booked(staff, date, start_time, duration_minutes):
    """
    Check if a time slot is already booked for staff
    """
    end_time = add_minutes_to_time(start_time, duration_minutes)

    # Check for overlapping bookings
    overlapping = Booking.objects.filter(
        staff=staff,
        date=date,
        status__in=['pending', 'confirmed', 'in_progress']
    ).filter(
        start_time__lt=end_time,
        end_time__gt=start_time
    )

    return overlapping.exists()


def validate_booking_availability(service, staff, date, start_time):
    """
    Validate if booking can be made

    Returns: (is_available: bool, error_message: str)
    """
    # Check if date is in the past
    if date < timezone.now().date():
        return False, "Cannot book in the past"

    # Check if date is today and time has passed
    if date == timezone.now().date():
        current_time = timezone.now().time()
        if start_time <= current_time:
            return False, "Cannot book a time that has already passed"

    # Get staff (or first available if not specified)
    if not staff:
        staff_members = service.staff_members.filter(is_active_for_bookings=True)
        if not staff_members.exists():
            return False, "No staff available for this service"
        staff = staff_members.first()

    # Check staff availability
    staff_availability = get_staff_availability(staff, date)
    if not staff_availability:
        return False, f"Staff {staff} is not available on this date"

    # Check if time is within working hours
    if not is_time_in_range(start_time, staff_availability['start_time'], staff_availability['end_time']):
        return False, f"Time is outside staff working hours ({staff_availability['start_time']} - {staff_availability['end_time']})"

    # Check if not in break time
    if staff_availability.get('break_start') and staff_availability.get('break_end'):
        if is_time_in_range(start_time, staff_availability['break_start'], staff_availability['break_end']):
            return False, f"Time conflicts with staff break time"

    # Check if end time is within working hours
    end_time = add_minutes_to_time(start_time, service.total_duration_minutes)
    if time_to_minutes(end_time) > time_to_minutes(staff_availability['end_time']):
        return False, "Booking would extend beyond staff working hours"

    # Check if slot is already booked
    if is_slot_booked(staff, date, start_time, service.total_duration_minutes):
        return False, "This time slot is already booked"

    return True, ""


def is_time_in_range(check_time, start_time, end_time):
    """Check if time is within range"""
    return start_time <= check_time < end_time


def time_to_minutes(t):
    """Convert time to minutes since midnight"""
    return t.hour * 60 + t.minute


def add_minutes_to_time(t, minutes):
    """Add minutes to a time object"""
    dt = datetime.combine(datetime.today(), t)
    dt = dt + timedelta(minutes=minutes)
    return dt.time()


def calculate_refund_amount(booking, settings):
    """
    Calculate refund amount based on cancellation policy

    Args:
        booking: Booking instance
        settings: BookingSettings instance

    Returns:
        Decimal: Refund amount
    """
    if booking.paid_amount == 0:
        return 0

    # Check cancellation policy
    if settings.refund_policy == 'full':
        return booking.paid_amount
    elif settings.refund_policy == 'partial_50':
        return booking.paid_amount * 0.5
    elif settings.refund_policy == 'partial_25':
        return booking.paid_amount * 0.25
    else:  # no_refund
        return 0


def can_cancel_booking(booking, settings):
    """
    Check if booking can be cancelled based on time policy

    Returns: (can_cancel: bool, reason: str)
    """
    if booking.status in ['completed', 'cancelled']:
        return False, "Booking is already completed or cancelled"

    # Calculate time until booking
    booking_datetime = datetime.combine(booking.date, booking.start_time)
    now = timezone.now()
    time_until_booking = booking_datetime - now.replace(tzinfo=None)

    # Check minimum cancellation time
    min_hours = timedelta(hours=settings.cancellation_hours_before)
    if time_until_booking < min_hours:
        return False, f"Bookings must be cancelled at least {settings.cancellation_hours_before} hours in advance"

    return True, ""
