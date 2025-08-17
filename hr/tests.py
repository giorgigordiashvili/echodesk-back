from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import date, timedelta

from .models import (
    WorkSchedule, LeaveType, EmployeeLeaveBalance, LeaveRequest,
    EmployeeWorkSchedule, Holiday
)

User = get_user_model()


class HRSystemTestCase(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create test user
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        
        # Create work schedule
        self.work_schedule = WorkSchedule.objects.create(
            name='Test Schedule',
            schedule_type='standard',
            hours_per_day=Decimal('8.0'),
            hours_per_week=Decimal('40.0'),
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=False,
            sunday=False,
            start_time='09:00',
            end_time='18:00',
            break_duration_minutes=60
        )
        
        # Assign work schedule to user
        EmployeeWorkSchedule.objects.create(
            employee=self.user,
            work_schedule=self.work_schedule,
            effective_from=timezone.now().date(),
            is_active=True
        )
        
        # Create leave type
        self.leave_type = LeaveType.objects.create(
            name='Annual Leave',
            category='annual',
            max_days_per_year=Decimal('21.0'),
            requires_approval=True,
            min_notice_days=7,
            is_active=True,
            is_paid=True
        )
        
        # Create leave balance
        self.leave_balance = EmployeeLeaveBalance.objects.create(
            employee=self.user,
            leave_type=self.leave_type,
            year=timezone.now().year,
            allocated_days=Decimal('21.0'),
            used_days=Decimal('0.0'),
            pending_days=Decimal('0.0'),
            carried_over_days=Decimal('0.0')
        )

    def test_work_schedule_creation(self):
        """Test work schedule model"""
        self.assertEqual(self.work_schedule.working_days_count, 5)
        self.assertEqual(self.work_schedule.hours_per_week, Decimal('40.0'))
        working_days = self.work_schedule.get_working_days_list()
        expected_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        self.assertEqual(working_days, expected_days)

    def test_leave_type_creation(self):
        """Test leave type model"""
        self.assertEqual(self.leave_type.name, 'Annual Leave')
        self.assertEqual(self.leave_type.category, 'annual')
        self.assertTrue(self.leave_type.requires_approval)

    def test_leave_balance_calculation(self):
        """Test leave balance calculations"""
        self.assertEqual(self.leave_balance.available_days, Decimal('21.0'))
        self.assertEqual(self.leave_balance.total_allocated, Decimal('21.0'))
        self.assertTrue(self.leave_balance.can_take_leave(Decimal('5.0')))
        self.assertFalse(self.leave_balance.can_take_leave(Decimal('25.0')))

    def test_leave_request_creation(self):
        """Test leave request creation and validation"""
        start_date = date.today() + timedelta(days=10)
        end_date = start_date + timedelta(days=4)  # 5 working days
        
        leave_request = LeaveRequest.objects.create(
            employee=self.user,
            leave_type=self.leave_type,
            start_date=start_date,
            end_date=end_date,
            duration_type='full_day',
            reason='Test vacation'
        )
        
        # Check that working days are calculated correctly
        self.assertEqual(leave_request.working_days_count, Decimal('5.0'))
        self.assertEqual(leave_request.total_days, 5)

    def test_leave_request_validation(self):
        """Test leave request business rules"""
        # Test with sufficient notice
        start_date = date.today() + timedelta(days=10)
        end_date = start_date + timedelta(days=2)
        
        leave_request = LeaveRequest.objects.create(
            employee=self.user,
            leave_type=self.leave_type,
            start_date=start_date,
            end_date=end_date,
            duration_type='full_day',
            reason='Test leave',
            status='draft'
        )
        
        can_submit, message = leave_request.can_be_submitted()
        self.assertTrue(can_submit)

    def test_leave_request_insufficient_notice(self):
        """Test leave request with insufficient notice"""
        # Test with insufficient notice (less than 7 days)
        start_date = date.today() + timedelta(days=3)
        end_date = start_date + timedelta(days=1)
        
        leave_request = LeaveRequest.objects.create(
            employee=self.user,
            leave_type=self.leave_type,
            start_date=start_date,
            end_date=end_date,
            duration_type='full_day',
            reason='Test leave',
            status='draft'
        )
        
        can_submit, message = leave_request.can_be_submitted()
        self.assertFalse(can_submit)
        self.assertIn('notice required', message)

    def test_leave_request_submission(self):
        """Test leave request submission workflow"""
        start_date = date.today() + timedelta(days=10)
        end_date = start_date + timedelta(days=2)
        
        leave_request = LeaveRequest.objects.create(
            employee=self.user,
            leave_type=self.leave_type,
            start_date=start_date,
            end_date=end_date,
            duration_type='full_day',
            reason='Test leave',
            status='draft'
        )
        
        # Submit the request
        leave_request.submit()
        
        # Check status change
        self.assertEqual(leave_request.status, 'submitted')
        self.assertIsNotNone(leave_request.submitted_at)
        
        # Check that pending days are updated in balance
        self.leave_balance.refresh_from_db()
        self.assertEqual(self.leave_balance.pending_days, leave_request.working_days_count)

    def test_leave_request_approval(self):
        """Test leave request approval workflow"""
        # Create manager user
        manager = User.objects.create_user(
            email='manager@example.com',
            password='testpass123',
            first_name='Manager',
            last_name='User',
            can_manage_users=True
        )
        
        start_date = date.today() + timedelta(days=10)
        end_date = start_date + timedelta(days=2)
        
        leave_request = LeaveRequest.objects.create(
            employee=self.user,
            leave_type=self.leave_type,
            start_date=start_date,
            end_date=end_date,
            duration_type='full_day',
            reason='Test leave',
            status='submitted'
        )
        
        # Update balance to reflect submission
        self.leave_balance.pending_days = leave_request.working_days_count
        self.leave_balance.save()
        
        # Approve the request
        leave_request.approve(manager, 'Approved for test')
        
        # Check status and approval details
        self.assertEqual(leave_request.status, 'approved')
        self.assertEqual(leave_request.approved_by, manager)
        self.assertIsNotNone(leave_request.approval_date)
        
        # Check that balance is updated correctly
        self.leave_balance.refresh_from_db()
        self.assertEqual(self.leave_balance.used_days, leave_request.working_days_count)
        self.assertEqual(self.leave_balance.pending_days, Decimal('0.0'))

    def test_half_day_leave_calculation(self):
        """Test half-day leave calculation"""
        start_date = date.today() + timedelta(days=10)
        
        leave_request = LeaveRequest.objects.create(
            employee=self.user,
            leave_type=self.leave_type,
            start_date=start_date,
            end_date=start_date,  # Same day
            duration_type='half_day_morning',
            reason='Medical appointment'
        )
        
        self.assertEqual(leave_request.working_days_count, Decimal('0.5'))
        self.assertEqual(leave_request.total_days, Decimal('0.5'))

    def test_weekend_calculation(self):
        """Test that weekends are not counted in working days"""
        # Find next Monday
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        start_date = today + timedelta(days=days_until_monday)  # Monday
        end_date = start_date + timedelta(days=6)  # Sunday
        
        leave_request = LeaveRequest.objects.create(
            employee=self.user,
            leave_type=self.leave_type,
            start_date=start_date,
            end_date=end_date,
            duration_type='full_day',
            reason='Week off'
        )
        
        # Should only count Monday-Friday (5 working days)
        self.assertEqual(leave_request.working_days_count, Decimal('5.0'))


class LeaveBalanceTestCase(TestCase):
    def setUp(self):
        """Set up test data for balance tests"""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        
        self.leave_type = LeaveType.objects.create(
            name='Test Leave',
            category='annual',
            max_days_per_year=Decimal('20.0'),
            allow_carry_over=True,
            max_carry_over_days=Decimal('5.0'),
            is_active=True
        )

    def test_carry_over_calculation(self):
        """Test carry over calculation from previous year"""
        current_year = timezone.now().year
        
        # Create previous year balance with remaining days
        prev_balance = EmployeeLeaveBalance.objects.create(
            employee=self.user,
            leave_type=self.leave_type,
            year=current_year - 1,
            allocated_days=Decimal('20.0'),
            used_days=Decimal('15.0'),  # 5 days remaining
            pending_days=Decimal('0.0'),
            carried_over_days=Decimal('0.0')
        )
        
        # Create current year balance
        current_balance = EmployeeLeaveBalance.objects.create(
            employee=self.user,
            leave_type=self.leave_type,
            year=current_year,
            allocated_days=Decimal('20.0'),
            used_days=Decimal('0.0'),
            pending_days=Decimal('0.0'),
            carried_over_days=Decimal('5.0')  # Carried over from previous year
        )
        
        # Total allocated should include carry over
        self.assertEqual(current_balance.total_allocated, Decimal('25.0'))
        self.assertEqual(current_balance.available_days, Decimal('25.0'))
