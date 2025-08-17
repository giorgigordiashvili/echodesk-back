from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import calendar

User = get_user_model()


class WorkSchedule(models.Model):
    """
    Defines work schedules for employees.
    Different employees can have different work patterns.
    """
    SCHEDULE_TYPE_CHOICES = [
        ('standard', 'Standard (Mon-Fri)'),
        ('custom', 'Custom Days'),
        ('shift', 'Shift Work'),
        ('flexible', 'Flexible Hours'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    schedule_type = models.CharField(max_length=20, choices=SCHEDULE_TYPE_CHOICES, default='standard')
    
    # Standard schedule settings
    hours_per_day = models.DecimalField(max_digits=4, decimal_places=2, default=8.0)
    hours_per_week = models.DecimalField(max_digits=4, decimal_places=2, default=40.0)
    
    # Working days (for standard and custom types)
    monday = models.BooleanField(default=True)
    tuesday = models.BooleanField(default=True)
    wednesday = models.BooleanField(default=True)
    thursday = models.BooleanField(default=True)
    friday = models.BooleanField(default=True)
    saturday = models.BooleanField(default=False)
    sunday = models.BooleanField(default=False)
    
    # Time settings
    start_time = models.TimeField(default='09:00')
    end_time = models.TimeField(default='18:00')
    break_duration_minutes = models.IntegerField(default=60, help_text='Break duration in minutes')
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.hours_per_week}h/week)"
    
    @property
    def working_days_count(self):
        """Count of working days per week"""
        days = [self.monday, self.tuesday, self.wednesday, self.thursday, 
                self.friday, self.saturday, self.sunday]
        return sum(days)
    
    def get_working_days_list(self):
        """Get list of working day names"""
        days = []
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        working_days = [self.monday, self.tuesday, self.wednesday, self.thursday, 
                       self.friday, self.saturday, self.sunday]
        
        for i, is_working in enumerate(working_days):
            if is_working:
                days.append(day_names[i])
        return days


class LeaveType(models.Model):
    """
    Defines different types of leaves available to employees.
    """
    LEAVE_CATEGORY_CHOICES = [
        ('annual', 'Annual Leave'),
        ('sick', 'Sick Leave'),
        ('maternity', 'Maternity Leave'),
        ('paternity', 'Paternity Leave'),
        ('personal', 'Personal Leave'),
        ('emergency', 'Emergency Leave'),
        ('study', 'Study Leave'),
        ('unpaid', 'Unpaid Leave'),
        ('compensation', 'Compensation Leave'),
        ('bereavement', 'Bereavement Leave'),
    ]
    
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=LEAVE_CATEGORY_CHOICES)
    
    # Leave allocation settings
    max_days_per_year = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        help_text='Maximum days allowed per year (0.5 = half day)'
    )
    
    # Carry over settings
    allow_carry_over = models.BooleanField(default=False, help_text='Allow unused days to carry over to next year')
    max_carry_over_days = models.DecimalField(
        max_digits=5, 
        decimal_places=1, 
        default=0,
        help_text='Maximum days that can be carried over'
    )
    
    # Request settings
    requires_approval = models.BooleanField(default=True)
    min_notice_days = models.IntegerField(default=7, help_text='Minimum days notice required')
    max_consecutive_days = models.IntegerField(null=True, blank=True, help_text='Maximum consecutive days allowed')
    
    # Documentation requirements
    requires_medical_certificate = models.BooleanField(default=False)
    medical_certificate_threshold_days = models.IntegerField(
        null=True, 
        blank=True,
        help_text='Days threshold for requiring medical certificate'
    )
    
    # Eligibility
    minimum_service_months = models.IntegerField(default=0, help_text='Minimum months of service required')
    available_to_probationary = models.BooleanField(default=True)
    
    # Gender specific (for maternity/paternity)
    gender_specific = models.CharField(
        max_length=10,
        choices=[('male', 'Male'), ('female', 'Female'), ('all', 'All')],
        default='all'
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    is_paid = models.BooleanField(default=True)
    
    # Color for UI
    color_code = models.CharField(max_length=7, default='#3B82F6', help_text='Hex color code for UI display')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.max_days_per_year} days/year)"


class EmployeeLeaveBalance(models.Model):
    """
    Tracks leave balances for each employee per leave type per year.
    """
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_balances')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.IntegerField()
    
    # Balance tracking
    allocated_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    used_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    pending_days = models.DecimalField(max_digits=5, decimal_places=1, default=0, help_text='Days in pending requests')
    carried_over_days = models.DecimalField(max_digits=5, decimal_places=1, default=0, help_text='Days carried over from previous year')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['employee', 'leave_type', 'year']
        ordering = ['-year', 'leave_type__category', 'leave_type__name']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.leave_type.name} ({self.year})"
    
    @property
    def available_days(self):
        """Calculate available leave days"""
        return self.allocated_days + self.carried_over_days - self.used_days - self.pending_days
    
    @property
    def total_allocated(self):
        """Total allocated including carried over"""
        return self.allocated_days + self.carried_over_days
    
    def can_take_leave(self, days_requested):
        """Check if employee can take the requested days"""
        return self.available_days >= days_requested


class LeaveRequest(models.Model):
    """
    Individual leave requests from employees.
    """
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
    ]
    
    DURATION_TYPE_CHOICES = [
        ('full_day', 'Full Day'),
        ('half_day_morning', 'Half Day - Morning'),
        ('half_day_afternoon', 'Half Day - Afternoon'),
        ('hours', 'Specific Hours'),
    ]
    
    # Basic information
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    
    # Request details
    start_date = models.DateField()
    end_date = models.DateField()
    duration_type = models.CharField(max_length=20, choices=DURATION_TYPE_CHOICES, default='full_day')
    
    # For hourly requests
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    
    # Calculated fields
    total_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    working_days_count = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    
    # Request information
    reason = models.TextField(help_text='Reason for leave request')
    emergency_contact = models.CharField(max_length=100, blank=True, help_text='Emergency contact during leave')
    handover_notes = models.TextField(blank=True, help_text='Work handover details')
    
    # Approval workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_leave_requests'
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    approval_comments = models.TextField(blank=True)
    
    # Documentation
    medical_certificate = models.FileField(
        upload_to='leave_certificates/',
        null=True, 
        blank=True,
        help_text='Medical certificate if required'
    )
    supporting_documents = models.FileField(
        upload_to='leave_documents/',
        null=True, 
        blank=True,
        help_text='Any supporting documents'
    )
    
    # Timestamps
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.leave_type.name} ({self.start_date} to {self.end_date})"
    
    def clean(self):
        """Validate leave request"""
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError("Start date cannot be after end date")
            
            # Check if start date is in the past (except for emergency leaves)
            if self.start_date < timezone.now().date() and self.leave_type.category != 'emergency':
                if self.status in ['draft', 'submitted']:
                    raise ValidationError("Cannot request leave for past dates")
        
        # Validate time fields for hourly requests
        if self.duration_type == 'hours':
            if not self.start_time or not self.end_time:
                raise ValidationError("Start time and end time are required for hourly requests")
            if self.start_time >= self.end_time:
                raise ValidationError("Start time must be before end time")
    
    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            self.calculate_days()
        super().save(*args, **kwargs)
    
    def calculate_days(self):
        """Calculate total days and working days for the leave request"""
        if not self.start_date or not self.end_date:
            return
        
        # Get employee's work schedule
        try:
            schedule = EmployeeWorkSchedule.objects.get(
                employee=self.employee,
                is_active=True
            ).work_schedule
        except EmployeeWorkSchedule.DoesNotExist:
            # Use default schedule if none assigned
            schedule = WorkSchedule.objects.filter(name='Standard').first()
            if not schedule:
                # Fallback to Monday-Friday if no standard schedule exists
                self.working_days_count = self._calculate_working_days_default()
                self.total_days = (self.end_date - self.start_date).days + 1
                return
        
        # Calculate based on duration type
        if self.duration_type == 'full_day':
            self.working_days_count = self._calculate_working_days(schedule)
            self.total_days = (self.end_date - self.start_date).days + 1
        elif self.duration_type in ['half_day_morning', 'half_day_afternoon']:
            # Half day is 0.5 days
            self.working_days_count = Decimal('0.5')
            self.total_days = Decimal('0.5')
        elif self.duration_type == 'hours':
            # Calculate based on hours
            if self.start_time and self.end_time:
                hours_requested = (
                    timezone.datetime.combine(timezone.now().date(), self.end_time) -
                    timezone.datetime.combine(timezone.now().date(), self.start_time)
                ).total_seconds() / 3600
                
                # Convert hours to days based on schedule
                days_fraction = Decimal(str(hours_requested)) / schedule.hours_per_day
                self.working_days_count = round(days_fraction, 1)
                self.total_days = self.working_days_count
    
    def _calculate_working_days(self, schedule):
        """Calculate working days based on schedule"""
        working_days = 0
        current_date = self.start_date
        
        # Map weekdays to schedule fields
        schedule_days = [
            schedule.monday, schedule.tuesday, schedule.wednesday, 
            schedule.thursday, schedule.friday, schedule.saturday, schedule.sunday
        ]
        
        while current_date <= self.end_date:
            weekday = current_date.weekday()  # Monday = 0, Sunday = 6
            if schedule_days[weekday]:
                working_days += 1
            current_date += timedelta(days=1)
        
        return Decimal(str(working_days))
    
    def _calculate_working_days_default(self):
        """Calculate working days using default Monday-Friday schedule"""
        working_days = 0
        current_date = self.start_date
        
        while current_date <= self.end_date:
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                working_days += 1
            current_date += timedelta(days=1)
        
        return Decimal(str(working_days))
    
    def can_be_submitted(self):
        """Check if request can be submitted"""
        if self.status != 'draft':
            return False, "Request is not in draft status"
        
        # Check minimum notice period
        notice_days = (self.start_date - timezone.now().date()).days
        if notice_days < self.leave_type.min_notice_days and self.leave_type.category != 'emergency':
            return False, f"Minimum {self.leave_type.min_notice_days} days notice required"
        
        # Check leave balance
        try:
            balance = EmployeeLeaveBalance.objects.get(
                employee=self.employee,
                leave_type=self.leave_type,
                year=self.start_date.year
            )
            if not balance.can_take_leave(self.working_days_count):
                return False, "Insufficient leave balance"
        except EmployeeLeaveBalance.DoesNotExist:
            return False, "No leave balance found for this year"
        
        return True, "Can be submitted"
    
    def submit(self):
        """Submit the leave request"""
        can_submit, message = self.can_be_submitted()
        if not can_submit:
            raise ValidationError(message)
        
        self.status = 'submitted' if self.leave_type.requires_approval else 'approved'
        self.submitted_at = timezone.now()
        
        # If auto-approved, set approval details
        if self.status == 'approved':
            self.approved_by = self.employee  # Auto-approval
            self.approval_date = timezone.now()
            self.approval_comments = "Auto-approved (no approval required)"
        
        self.save()
        
        # Update leave balance pending days
        self._update_leave_balance('add_pending')
    
    def approve(self, approved_by, comments=''):
        """Approve the leave request"""
        if self.status not in ['submitted', 'pending_approval']:
            raise ValidationError("Only submitted requests can be approved")
        
        self.status = 'approved'
        self.approved_by = approved_by
        self.approval_date = timezone.now()
        self.approval_comments = comments
        self.save()
        
        # Convert pending to used in leave balance
        self._update_leave_balance('approve')
    
    def reject(self, rejected_by, comments=''):
        """Reject the leave request"""
        if self.status not in ['submitted', 'pending_approval']:
            raise ValidationError("Only submitted requests can be rejected")
        
        self.status = 'rejected'
        self.approved_by = rejected_by
        self.approval_date = timezone.now()
        self.approval_comments = comments
        self.save()
        
        # Remove from pending in leave balance
        self._update_leave_balance('remove_pending')
    
    def cancel(self):
        """Cancel the leave request"""
        if self.status in ['completed', 'cancelled']:
            raise ValidationError("Cannot cancel completed or already cancelled requests")
        
        old_status = self.status
        self.status = 'cancelled'
        self.save()
        
        # Update leave balance based on previous status
        if old_status in ['submitted', 'pending_approval']:
            self._update_leave_balance('remove_pending')
        elif old_status == 'approved':
            self._update_leave_balance('cancel_approved')
    
    def _update_leave_balance(self, action):
        """Update employee leave balance"""
        try:
            balance = EmployeeLeaveBalance.objects.get(
                employee=self.employee,
                leave_type=self.leave_type,
                year=self.start_date.year
            )
            
            if action == 'add_pending':
                balance.pending_days += self.working_days_count
            elif action == 'remove_pending':
                balance.pending_days = max(0, balance.pending_days - self.working_days_count)
            elif action == 'approve':
                balance.pending_days = max(0, balance.pending_days - self.working_days_count)
                balance.used_days += self.working_days_count
            elif action == 'cancel_approved':
                balance.used_days = max(0, balance.used_days - self.working_days_count)
            
            balance.save()
        except EmployeeLeaveBalance.DoesNotExist:
            pass


class EmployeeWorkSchedule(models.Model):
    """
    Links employees to their work schedules.
    """
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='work_schedules')
    work_schedule = models.ForeignKey(WorkSchedule, on_delete=models.CASCADE)
    
    effective_from = models.DateField(default=timezone.now)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-effective_from']
    
    def __str__(self):
        return f"{self.employee.get_full_name()} - {self.work_schedule.name}"
    
    def clean(self):
        if self.effective_to and self.effective_from >= self.effective_to:
            raise ValidationError("Effective from date must be before effective to date")


class Holiday(models.Model):
    """
    Public holidays that affect leave calculations.
    """
    name = models.CharField(max_length=100)
    date = models.DateField()
    is_recurring = models.BooleanField(default=False, help_text='Occurs every year on the same date')
    description = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['name', 'date']
        ordering = ['date']
    
    def __str__(self):
        return f"{self.name} ({self.date})"


class LeaveRequestComment(models.Model):
    """
    Comments on leave requests for approval workflow.
    """
    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField()
    is_internal = models.BooleanField(default=False, help_text='Internal comment not visible to employee')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.author.get_full_name()} on {self.leave_request}"
