# HR Vacation Leave Management System

## Overview

This HR module provides comprehensive vacation leave management functionality for the EchoDesk platform. It allows tenant employees to request various types of leaves, managers to approve/reject requests, and provides detailed reporting and analytics.

## Features

### 🏗️ Core Components

1. **Work Schedules** - Define different work patterns for employees
2. **Leave Types** - Configure various types of leaves with specific rules
3. **Leave Balances** - Track employee leave allocations and usage
4. **Leave Requests** - Employee leave request workflow
5. **Approval System** - Manager approval/rejection workflow
6. **Reports & Analytics** - Comprehensive leave reporting

### 👥 User Roles

- **Employees**: Can view balances, submit requests, and track their leave history
- **Managers**: Can approve/reject requests, view team reports, and manage employee schedules
- **HR Admins**: Can configure leave types, work schedules, and view all reports

## API Endpoints

### Work Schedules
```
GET    /api/hr/work-schedules/          # List all work schedules
POST   /api/hr/work-schedules/          # Create new work schedule
GET    /api/hr/work-schedules/{id}/     # Get specific work schedule
PUT    /api/hr/work-schedules/{id}/     # Update work schedule
DELETE /api/hr/work-schedules/{id}/     # Delete work schedule
```

### Leave Types
```
GET    /api/hr/leave-types/             # List all leave types
POST   /api/hr/leave-types/             # Create new leave type
GET    /api/hr/leave-types/{id}/        # Get specific leave type
PUT    /api/hr/leave-types/{id}/        # Update leave type
DELETE /api/hr/leave-types/{id}/        # Delete leave type
```

### Leave Balances
```
GET    /api/hr/leave-balances/          # List leave balances
POST   /api/hr/leave-balances/          # Create/update balance
GET    /api/hr/leave-balances/{id}/     # Get specific balance
GET    /api/hr/leave-balances/my_balances/  # Get current user's balances
POST   /api/hr/leave-balances/initialize_year/  # Initialize balances for year
```

### Leave Requests
```
GET    /api/hr/leave-requests/          # List leave requests
POST   /api/hr/leave-requests/          # Create new leave request
GET    /api/hr/leave-requests/{id}/     # Get specific request
PUT    /api/hr/leave-requests/{id}/     # Update request
DELETE /api/hr/leave-requests/{id}/     # Delete request

# Special actions
POST   /api/hr/leave-requests/{id}/submit/       # Submit request
POST   /api/hr/leave-requests/{id}/approve_reject/  # Approve/reject request
POST   /api/hr/leave-requests/{id}/cancel/       # Cancel request
POST   /api/hr/leave-requests/{id}/add_comment/  # Add comment

# Filtered views
GET    /api/hr/leave-requests/my_requests/       # Current user's requests
GET    /api/hr/leave-requests/pending_approval/  # Requests pending approval
GET    /api/hr/leave-requests/calendar_view/     # Calendar format
```

### Employee Work Schedules
```
GET    /api/hr/employee-schedules/      # List employee schedules
POST   /api/hr/employee-schedules/      # Assign schedule to employee
GET    /api/hr/employee-schedules/{id}/ # Get specific assignment
PUT    /api/hr/employee-schedules/{id}/ # Update assignment
GET    /api/hr/employee-schedules/my_schedule/  # Current user's schedule
```

### Holidays
```
GET    /api/hr/holidays/               # List holidays
POST   /api/hr/holidays/               # Create holiday
GET    /api/hr/holidays/{id}/          # Get specific holiday
PUT    /api/hr/holidays/{id}/          # Update holiday
DELETE /api/hr/holidays/{id}/          # Delete holiday
GET    /api/hr/holidays/current_year/  # Get holidays for specific year
```

### Reports
```
GET    /api/hr/reports/employee_summary/  # Employee leave summary report
GET    /api/hr/reports/leave_trends/      # Leave trends and analytics
```

## Models

### WorkSchedule
Defines work patterns for employees:
- **schedule_type**: standard, custom, shift, flexible
- **working_days**: Monday-Sunday boolean flags
- **hours_per_day/week**: Working hours configuration
- **start_time/end_time**: Default work hours

### LeaveType
Configures different types of leaves:
- **category**: annual, sick, maternity, paternity, personal, emergency, study, unpaid, bereavement
- **max_days_per_year**: Maximum days allowed per year
- **requires_approval**: Whether manager approval is needed
- **min_notice_days**: Minimum advance notice required
- **carry_over settings**: Rules for carrying over unused days

### EmployeeLeaveBalance
Tracks employee leave balances:
- **allocated_days**: Total days allocated for the year
- **used_days**: Days already taken
- **pending_days**: Days in pending requests
- **carried_over_days**: Days carried from previous year
- **available_days**: Calculated available days

### LeaveRequest
Individual leave requests:
- **duration_type**: full_day, half_day_morning, half_day_afternoon, hours
- **status**: draft, submitted, pending_approval, approved, rejected, cancelled, completed
- **approval workflow**: Approved by, approval date, comments
- **document support**: Medical certificates, supporting documents

## Usage Examples

### 1. Creating a Leave Request

```python
# POST /api/hr/leave-requests/
{
    "leave_type": 1,  # Annual Leave
    "start_date": "2024-12-20",
    "end_date": "2024-12-24",
    "duration_type": "full_day",
    "reason": "Christmas vacation with family",
    "emergency_contact": "John Doe - +995555123456"
}
```

### 2. Submitting a Leave Request

```python
# POST /api/hr/leave-requests/123/submit/
{
    # No body required - will validate and submit
}
```

### 3. Approving a Leave Request

```python
# POST /api/hr/leave-requests/123/approve_reject/
{
    "action": "approve",
    "comments": "Approved for Christmas period"
}
```

### 4. Getting Employee's Leave Balance

```python
# GET /api/hr/leave-balances/my_balances/?year=2024
[
    {
        "leave_type_name": "Annual Leave",
        "allocated_days": "21.0",
        "used_days": "5.0",
        "pending_days": "3.0",
        "available_days": "13.0"
    }
]
```

## Default Leave Types

The system comes with pre-configured leave types:

1. **Annual Leave** - 21 days/year, carry over allowed (5 days max)
2. **Sick Leave** - 10 days/year, medical certificate required for 3+ days
3. **Maternity Leave** - 126 days/year (18 weeks), female only
4. **Paternity Leave** - 14 days/year (2 weeks), male only
5. **Personal Leave** - 3 days/year, no carry over
6. **Emergency Leave** - 2 days/year, no approval required
7. **Study Leave** - 5 days/year, carry over allowed
8. **Unpaid Leave** - 30 days/year, unpaid
9. **Bereavement Leave** - 3 days/year, no approval required

## Setup Instructions

### 1. Initialize HR System

Run the management command to create default work schedules and leave types:

```bash
python manage.py init_hr_system
```

### 2. Initialize Leave Balances

Initialize leave balances for all employees for the current year:

```bash
python manage.py init_leave_balances --year 2024
```

### 3. Assign Work Schedules

Assign work schedules to employees through the admin interface or API.

## Permissions

The system integrates with the existing user permission system:

- **Regular employees**: Can only see their own data
- **Managers** (`can_manage_users=True`): Can see team data and approve requests
- **Staff users** (`is_staff=True`): Can see all data and configure system

## Calendar Integration

The system provides calendar-formatted data for frontend integration:

```python
# GET /api/hr/leave-requests/calendar_view/?start=2024-01-01&end=2024-12-31
[
    {
        "id": 123,
        "title": "John Doe - Annual Leave",
        "start": "2024-12-20",
        "end": "2024-12-25",
        "color": "#3B82F6",
        "employee": "John Doe",
        "leave_type": "Annual Leave",
        "total_days": 5.0
    }
]
```

## Reporting Features

### Employee Summary Report
- Leave balance by employee and type
- Total requests, approved, pending, rejected counts
- Days taken by category

### Leave Trends
- Monthly leave trends
- Leave type distribution
- Department-wise analytics

## Business Rules

1. **Notice Period**: Minimum notice periods vary by leave type
2. **Medical Certificates**: Required for sick leave >3 days
3. **Carry Over**: Only certain leave types allow carry over
4. **Consecutive Days**: Some leave types have maximum consecutive day limits
5. **Service Requirements**: Minimum service periods for certain leaves
6. **Gender Restrictions**: Maternity/Paternity leaves are gender-specific

## Error Handling

The system provides comprehensive validation:
- Date validation (start < end, not in past except emergencies)
- Balance validation (sufficient leave balance)
- Notice period validation
- Work schedule integration for calculating working days

## Integration Points

- **User Management**: Integrates with existing User and Department models
- **Permissions**: Uses existing permission system
- **Multi-tenancy**: Fully compatible with tenant schema isolation
- **Admin Interface**: Comprehensive admin interface for configuration

## Future Enhancements

- Email notifications for leave requests and approvals
- Mobile app integration
- Advanced workflow with multiple approval levels
- Integration with payroll systems
- Automated policy compliance checking
