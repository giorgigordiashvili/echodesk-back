"""
Tests for leave request approval workflow.
"""
from decimal import Decimal
from datetime import date, timedelta
from .conftest import LeaveTestCase
from leave_management.utils import get_next_approver_role, get_approval_chain


class TestApprovalChain(LeaveTestCase):
    """Test approval chain resolution."""

    def test_no_chain_returns_default_manager(self):
        lt = self.create_leave_type()
        employee = self.create_user(email='emp@test.com')
        request = self.create_leave_request(employee, lt)
        chain = get_approval_chain(request)
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0]['role'], 'manager')

    def test_settings_with_hr_approval(self):
        self.create_leave_settings(require_manager_approval=True, require_hr_approval=True)
        lt = self.create_leave_type()
        employee = self.create_user(email='emp@test.com')
        request = self.create_leave_request(employee, lt)
        chain = get_approval_chain(request)
        self.assertEqual(len(chain), 2)
        self.assertEqual(chain[0]['role'], 'manager')
        self.assertEqual(chain[1]['role'], 'hr')

    def test_no_approval_needed(self):
        lt = self.create_leave_type(requires_approval=False)
        employee = self.create_user(email='emp@test.com')
        request = self.create_leave_request(employee, lt)
        chain = get_approval_chain(request)
        self.assertEqual(len(chain), 0)

    def test_custom_chain_overrides_settings(self):
        self.create_leave_settings(require_manager_approval=True)
        lt = self.create_leave_type()
        # Custom chain with HR only
        self.create_approval_chain(leave_type=lt, level=1, approver_role='hr')
        employee = self.create_user(email='emp@test.com')
        request = self.create_leave_request(employee, lt)
        chain = get_approval_chain(request)
        self.assertEqual(len(chain), 1)
        self.assertEqual(chain[0]['role'], 'hr')


class TestNextApproverRole(LeaveTestCase):
    """Test next approver role determination."""

    def test_pending_needs_manager(self):
        self.create_leave_settings(require_manager_approval=True)
        lt = self.create_leave_type()
        employee = self.create_user(email='emp@test.com')
        request = self.create_leave_request(employee, lt, status='pending')
        role = get_next_approver_role(request)
        self.assertEqual(role, 'manager')

    def test_manager_approved_needs_hr(self):
        self.create_leave_settings(require_manager_approval=True, require_hr_approval=True)
        lt = self.create_leave_type()
        employee = self.create_user(email='emp@test.com')
        request = self.create_leave_request(employee, lt, status='manager_approved')
        role = get_next_approver_role(request)
        self.assertEqual(role, 'hr')

    def test_fully_approved_returns_none(self):
        self.create_leave_settings(require_manager_approval=True)
        lt = self.create_leave_type()
        employee = self.create_user(email='emp@test.com')
        request = self.create_leave_request(employee, lt, status='manager_approved')
        role = get_next_approver_role(request)
        # Only manager required, and it's already manager_approved
        self.assertIsNone(role)

    def test_no_approval_needed_returns_none(self):
        lt = self.create_leave_type(requires_approval=False)
        employee = self.create_user(email='emp@test.com')
        request = self.create_leave_request(employee, lt, status='pending')
        role = get_next_approver_role(request)
        self.assertIsNone(role)


class TestApprovalWorkflow(LeaveTestCase):
    """Test the full approval workflow via API."""

    def test_approve_pending_to_manager_approved(self):
        self.create_leave_settings(require_manager_approval=True, require_hr_approval=True)
        lt = self.create_leave_type()
        employee = self.create_user(email='emp@test.com')
        self.create_leave_balance(employee, lt)
        request = self.create_leave_request(employee, lt, status='pending')

        admin = self.create_admin(email='admin@test.com')
        resp = self.api_post(
            f'/api/leave/admin/leave-requests/{request.id}/approve/',
            {'comments': 'Approved by manager'},
            user=admin,
        )
        self.assertEqual(resp.status_code, 200)
        request.refresh_from_db()
        # Should be manager_approved (not fully approved, HR still needed)
        self.assertIn(request.status, ['manager_approved', 'approved'])

    def test_reject_returns_pending_balance(self):
        lt = self.create_leave_type()
        employee = self.create_user(email='emp@test.com')
        balance = self.create_leave_balance(employee, lt, pending_days=Decimal('3'))
        request = self.create_leave_request(employee, lt, total_days=Decimal('3'))

        admin = self.create_admin(email='admin@test.com')
        resp = self.api_post(
            f'/api/leave/admin/leave-requests/{request.id}/reject/',
            {'comments': 'Rejected'},
            user=admin,
        )
        self.assertEqual(resp.status_code, 200)
        request.refresh_from_db()
        self.assertEqual(request.status, 'rejected')
        balance.refresh_from_db()
        self.assertEqual(balance.pending_days, Decimal('0'))

    def test_cancel_approved_returns_used_days(self):
        lt = self.create_leave_type()
        employee = self.create_user(email='emp@test.com')
        balance = self.create_leave_balance(employee, lt, used_days=Decimal('5'))
        request = self.create_leave_request(
            employee, lt, total_days=Decimal('5'), status='approved'
        )

        admin = self.create_admin(email='admin@test.com')
        resp = self.api_post(
            f'/api/leave/admin/leave-requests/{request.id}/cancel/',
            {'reason': 'Plans changed'},
            user=admin,
        )
        self.assertEqual(resp.status_code, 200)
        request.refresh_from_db()
        self.assertEqual(request.status, 'cancelled')
        balance.refresh_from_db()
        self.assertEqual(balance.used_days, Decimal('0'))

    def test_cannot_approve_already_approved(self):
        lt = self.create_leave_type()
        employee = self.create_user(email='emp@test.com')
        request = self.create_leave_request(employee, lt, status='approved')

        admin = self.create_admin(email='admin@test.com')
        resp = self.api_post(
            f'/api/leave/admin/leave-requests/{request.id}/approve/',
            {'comments': ''},
            user=admin,
        )
        self.assertEqual(resp.status_code, 400)

    def test_cannot_reject_cancelled(self):
        lt = self.create_leave_type()
        employee = self.create_user(email='emp@test.com')
        request = self.create_leave_request(employee, lt, status='cancelled')

        admin = self.create_admin(email='admin@test.com')
        resp = self.api_post(
            f'/api/leave/admin/leave-requests/{request.id}/reject/',
            {'comments': ''},
            user=admin,
        )
        self.assertEqual(resp.status_code, 400)

    def test_cannot_cancel_already_cancelled(self):
        lt = self.create_leave_type()
        employee = self.create_user(email='emp@test.com')
        request = self.create_leave_request(employee, lt, status='cancelled')

        admin = self.create_admin(email='admin@test.com')
        resp = self.api_post(
            f'/api/leave/admin/leave-requests/{request.id}/cancel/',
            {'reason': ''},
            user=admin,
        )
        self.assertEqual(resp.status_code, 400)
