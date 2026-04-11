"""
Tests for leave balance calculations and updates.
"""
from decimal import Decimal
from datetime import date, timedelta
from .conftest import LeaveTestCase
from leave_management.utils import update_leave_balance, calculate_working_days
from leave_management.models import LeaveBalance


class TestBalanceCalculation(LeaveTestCase):
    """Test the available_days property calculation."""

    def test_available_days_basic(self):
        user = self.create_user(email='emp@test.com')
        lt = self.create_leave_type()
        balance = self.create_leave_balance(user, lt, allocated_days=Decimal('20'))
        self.assertEqual(balance.available_days, Decimal('20'))

    def test_available_days_with_used(self):
        user = self.create_user(email='emp@test.com')
        lt = self.create_leave_type()
        balance = self.create_leave_balance(user, lt, allocated_days=Decimal('20'), used_days=Decimal('5'))
        self.assertEqual(balance.available_days, Decimal('15'))

    def test_available_days_with_pending(self):
        user = self.create_user(email='emp@test.com')
        lt = self.create_leave_type()
        balance = self.create_leave_balance(user, lt, allocated_days=Decimal('20'), pending_days=Decimal('3'))
        self.assertEqual(balance.available_days, Decimal('17'))

    def test_available_days_with_carry_forward(self):
        user = self.create_user(email='emp@test.com')
        lt = self.create_leave_type()
        balance = self.create_leave_balance(
            user, lt, allocated_days=Decimal('20'), carried_forward_days=Decimal('5')
        )
        self.assertEqual(balance.available_days, Decimal('25'))

    def test_available_days_combined(self):
        user = self.create_user(email='emp@test.com')
        lt = self.create_leave_type()
        balance = self.create_leave_balance(
            user, lt,
            allocated_days=Decimal('20'),
            used_days=Decimal('8'),
            pending_days=Decimal('3'),
            carried_forward_days=Decimal('5'),
        )
        # 20 + 5 - 8 - 3 = 14
        self.assertEqual(balance.available_days, Decimal('14'))

    def test_available_days_can_be_negative(self):
        user = self.create_user(email='emp@test.com')
        lt = self.create_leave_type()
        balance = self.create_leave_balance(
            user, lt, allocated_days=Decimal('10'), used_days=Decimal('12')
        )
        self.assertEqual(balance.available_days, Decimal('-2'))


class TestUpdateLeaveBalance(LeaveTestCase):
    """Test the update_leave_balance utility function."""

    def setUp(self):
        super().setUp()
        self.employee = self.create_user(email='emp@test.com')
        self.leave_type = self.create_leave_type()
        self.balance = self.create_leave_balance(
            self.employee, self.leave_type, allocated_days=Decimal('20')
        )

    def _make_request(self, total_days=Decimal('3'), status='pending'):
        return self.create_leave_request(
            self.employee, self.leave_type, total_days=total_days, status=status
        )

    def test_pending_increments_pending_days(self):
        request = self._make_request(total_days=Decimal('5'))
        update_leave_balance(request, action='pending')
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.pending_days, Decimal('5'))

    def test_approve_moves_pending_to_used(self):
        self.balance.pending_days = Decimal('5')
        self.balance.save()
        request = self._make_request(total_days=Decimal('5'))
        update_leave_balance(request, action='approve')
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.pending_days, Decimal('0'))
        self.assertEqual(self.balance.used_days, Decimal('5'))

    def test_reject_removes_from_pending(self):
        self.balance.pending_days = Decimal('5')
        self.balance.save()
        request = self._make_request(total_days=Decimal('5'))
        update_leave_balance(request, action='reject')
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.pending_days, Decimal('0'))
        self.assertEqual(self.balance.used_days, Decimal('0'))

    def test_cancel_pending_removes_from_pending(self):
        self.balance.pending_days = Decimal('3')
        self.balance.save()
        request = self._make_request(total_days=Decimal('3'))
        update_leave_balance(request, action='cancel')
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.pending_days, Decimal('0'))
        self.assertEqual(self.balance.used_days, Decimal('0'))

    def test_cancel_approved_returns_used_days(self):
        self.balance.used_days = Decimal('5')
        self.balance.save()
        request = self._make_request(total_days=Decimal('5'), status='approved')
        update_leave_balance(request, action='cancel_approved')
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, Decimal('0'))

    def test_pending_days_never_negative(self):
        self.balance.pending_days = Decimal('0')
        self.balance.save()
        request = self._make_request(total_days=Decimal('5'))
        update_leave_balance(request, action='reject')
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.pending_days, Decimal('0'))

    def test_used_days_never_negative(self):
        self.balance.used_days = Decimal('0')
        self.balance.save()
        request = self._make_request(total_days=Decimal('5'), status='approved')
        update_leave_balance(request, action='cancel_approved')
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, Decimal('0'))

    def test_multiple_pending_requests(self):
        r1 = self._make_request(total_days=Decimal('3'))
        r2 = self._make_request(total_days=Decimal('5'))
        update_leave_balance(r1, action='pending')
        update_leave_balance(r2, action='pending')
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.pending_days, Decimal('8'))
        self.assertEqual(self.balance.available_days, Decimal('12'))


class TestWorkingDaysCalculation(LeaveTestCase):
    """Test working days calculation."""

    def test_weekday_range(self):
        # Monday to Friday = 5 working days
        start = date(2026, 4, 6)  # Monday
        end = date(2026, 4, 10)   # Friday
        days = calculate_working_days(start, end, self.tenant)
        self.assertEqual(days, Decimal('5'))

    def test_includes_weekend_excluded(self):
        # Monday to Sunday = 5 working days (Sat+Sun excluded)
        start = date(2026, 4, 6)   # Monday
        end = date(2026, 4, 12)    # Sunday
        days = calculate_working_days(start, end, self.tenant)
        self.assertEqual(days, Decimal('5'))

    def test_single_day(self):
        start = date(2026, 4, 6)  # Monday
        days = calculate_working_days(start, start, self.tenant)
        self.assertEqual(days, Decimal('1'))

    def test_weekend_day_returns_zero(self):
        start = date(2026, 4, 11)  # Saturday
        days = calculate_working_days(start, start, self.tenant)
        self.assertEqual(days, Decimal('0'))

    def test_start_after_end_returns_zero(self):
        start = date(2026, 4, 10)
        end = date(2026, 4, 6)
        days = calculate_working_days(start, end, self.tenant)
        self.assertEqual(days, Decimal('0'))

    def test_excludes_public_holidays(self):
        start = date(2026, 4, 6)  # Monday
        end = date(2026, 4, 10)   # Friday
        # Create a holiday on Wednesday
        self.create_public_holiday(date=date(2026, 4, 8))
        days = calculate_working_days(start, end, self.tenant)
        self.assertEqual(days, Decimal('4'))

    def test_two_week_range(self):
        start = date(2026, 4, 6)   # Monday
        end = date(2026, 4, 17)    # Friday
        days = calculate_working_days(start, end, self.tenant)
        self.assertEqual(days, Decimal('10'))
