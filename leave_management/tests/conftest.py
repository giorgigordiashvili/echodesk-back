"""
Shared test infrastructure for leave management tests.
Extends EchoDeskTenantTestCase with leave-specific helpers.
"""
from decimal import Decimal
from datetime import date, timedelta
from django.utils import timezone
from users.tests.conftest import EchoDeskTenantTestCase
from leave_management.models import (
    LeaveSettings, LeaveType, LeaveBalance, LeaveRequest,
    PublicHoliday, LeaveApprovalChain,
)


class LeaveTestCase(EchoDeskTenantTestCase):
    """
    Leave-specific test case with factory helpers for all leave models.
    """

    @staticmethod
    def get_results(resp):
        """Extract results from a paginated or non-paginated response."""
        if isinstance(resp.data, dict) and 'results' in resp.data:
            return resp.data['results']
        return resp.data

    def create_leave_settings(self, tenant=None, **kwargs):
        defaults = {
            'tenant': tenant or self.tenant,
            'require_manager_approval': True,
            'require_hr_approval': False,
            'allow_negative_balance': False,
            'max_negative_days': 0,
            'working_days_per_week': 5,
            'weekend_days': [5, 6],
        }
        defaults.update(kwargs)
        return LeaveSettings.objects.create(**defaults)

    def create_leave_type(self, tenant=None, **kwargs):
        defaults = {
            'tenant': tenant or self.tenant,
            'code': f'VAC{LeaveType.objects.count()}',
            'name': {'en': 'Vacation', 'ka': 'შვებულება'},
            'is_paid': True,
            'requires_approval': True,
            'calculation_method': 'annual',
            'default_days_per_year': Decimal('20'),
            'accrual_rate_per_month': Decimal('0'),
            'max_carry_forward_days': 5,
            'carry_forward_expiry_months': 3,
            'color': '#3B82F6',
            'is_active': True,
            'sort_order': 0,
        }
        defaults.update(kwargs)
        # created_by and updated_by
        if 'created_by' not in defaults:
            defaults['created_by'] = self.create_admin(
                email=f'lt-admin-{LeaveType.objects.count()}@test.com'
            )
        if 'updated_by' not in defaults:
            defaults['updated_by'] = defaults['created_by']
        return LeaveType.objects.create(**defaults)

    def create_leave_balance(self, user, leave_type, tenant=None, **kwargs):
        defaults = {
            'tenant': tenant or self.tenant,
            'user': user,
            'leave_type': leave_type,
            'year': date.today().year,
            'allocated_days': Decimal('20'),
            'used_days': Decimal('0'),
            'pending_days': Decimal('0'),
            'carried_forward_days': Decimal('0'),
        }
        defaults.update(kwargs)
        return LeaveBalance.objects.create(**defaults)

    def create_leave_request(self, employee, leave_type, tenant=None, **kwargs):
        today = date.today()
        defaults = {
            'tenant': tenant or self.tenant,
            'employee': employee,
            'leave_type': leave_type,
            'start_date': today + timedelta(days=7),
            'end_date': today + timedelta(days=9),
            'total_days': Decimal('3'),
            'reason': 'Test leave request',
            'status': 'pending',
        }
        defaults.update(kwargs)
        return LeaveRequest.objects.create(**defaults)

    def create_public_holiday(self, tenant=None, **kwargs):
        defaults = {
            'tenant': tenant or self.tenant,
            'name': {'en': 'New Year', 'ka': 'ახალი წელი'},
            'date': date(date.today().year, 1, 1),
            'is_recurring': True,
            'applies_to_all': True,
        }
        if 'created_by' not in defaults:
            defaults['created_by'] = self.create_admin(
                email=f'ph-admin-{PublicHoliday.objects.count()}@test.com'
            )
        if 'updated_by' not in defaults:
            defaults['updated_by'] = defaults['created_by']
        defaults.update(kwargs)
        return PublicHoliday.objects.create(**defaults)

    def create_approval_chain(self, leave_type=None, tenant=None, **kwargs):
        defaults = {
            'tenant': tenant or self.tenant,
            'leave_type': leave_type,
            'level': 1,
            'approver_role': 'manager',
            'is_required': True,
        }
        defaults.update(kwargs)
        return LeaveApprovalChain.objects.create(**defaults)
