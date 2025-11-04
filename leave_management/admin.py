from django.contrib import admin
from .models import (
    LeaveSettings, LeaveType, LeaveBalance, LeaveRequest,
    PublicHoliday, LeaveApprovalChain
)


class LeaveApprovalChainInline(admin.TabularInline):
    """Inline admin for approval chains"""
    model = LeaveApprovalChain
    extra = 0
    fields = ['level', 'approver_role', 'is_required']
    ordering = ['level']


@admin.register(LeaveSettings)
class LeaveSettingsAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'require_manager_approval', 'require_hr_approval',
                    'allow_negative_balance', 'max_negative_days', 'created_at']
    list_filter = ['require_manager_approval', 'require_hr_approval', 'allow_negative_balance']
    search_fields = ['tenant__name']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Tenant', {
            'fields': ('tenant',)
        }),
        ('Approval Settings', {
            'fields': ('require_manager_approval', 'require_hr_approval')
        }),
        ('Balance Settings', {
            'fields': ('allow_negative_balance', 'max_negative_days')
        }),
        ('Working Days', {
            'fields': ('working_days_per_week', 'weekend_days')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ['code', 'get_name', 'tenant', 'is_paid', 'requires_approval',
                    'calculation_method', 'is_active', 'sort_order']
    list_filter = ['tenant', 'is_active', 'is_paid', 'requires_approval', 'calculation_method']
    search_fields = ['code', 'name']
    ordering = ['tenant', 'sort_order', 'code']
    readonly_fields = ['created_by', 'updated_by', 'created_at', 'updated_at']
    inlines = [LeaveApprovalChainInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('tenant', 'code', 'name', 'description', 'color')
        }),
        ('Leave Type Settings', {
            'fields': ('is_paid', 'requires_approval', 'is_active', 'sort_order')
        }),
        ('Balance Calculation', {
            'fields': ('calculation_method', 'default_days_per_year', 'accrual_rate_per_month')
        }),
        ('Carry Forward Rules', {
            'fields': ('max_carry_forward_days', 'carry_forward_expiry_months')
        }),
        ('Audit', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_name(self, obj):
        return obj.get_name('en')
    get_name.short_description = 'Name'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ['user', 'leave_type', 'year', 'allocated_days', 'used_days',
                    'carried_forward_days', 'pending_days', 'get_available_days', 'tenant']
    list_filter = ['tenant', 'year', 'leave_type']
    search_fields = ['user__email', 'user__first_name', 'user__last_name']
    ordering = ['-year', 'user__last_name']
    readonly_fields = ['get_available_days', 'get_total_allocated', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Employee & Year', {
            'fields': ('tenant', 'user', 'leave_type', 'year')
        }),
        ('Balance Details', {
            'fields': ('allocated_days', 'used_days', 'carried_forward_days',
                      'pending_days', 'get_available_days', 'get_total_allocated')
        }),
        ('Accrual', {
            'fields': ('last_accrual_date',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_available_days(self, obj):
        return obj.available_days
    get_available_days.short_description = 'Available Days'

    def get_total_allocated(self, obj):
        return obj.total_allocated
    get_total_allocated.short_description = 'Total Allocated'


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['employee', 'leave_type', 'start_date', 'end_date', 'total_days',
                    'status', 'tenant', 'created_at']
    list_filter = ['tenant', 'status', 'leave_type', 'start_date', 'created_at']
    search_fields = ['employee__email', 'employee__first_name', 'employee__last_name', 'reason']
    ordering = ['-created_at']
    readonly_fields = ['total_days', 'created_at', 'updated_at']
    date_hierarchy = 'start_date'

    fieldsets = (
        ('Employee & Leave Type', {
            'fields': ('tenant', 'employee', 'leave_type')
        }),
        ('Leave Dates', {
            'fields': ('start_date', 'end_date', 'total_days')
        }),
        ('Request Details', {
            'fields': ('reason', 'attachment', 'status')
        }),
        ('Manager Approval', {
            'fields': ('manager_approver', 'manager_approved_at', 'manager_comments'),
            'classes': ('collapse',)
        }),
        ('HR Approval', {
            'fields': ('hr_approver', 'hr_approved_at', 'hr_comments'),
            'classes': ('collapse',)
        }),
        ('Final Approval', {
            'fields': ('final_approver', 'final_approved_at'),
            'classes': ('collapse',)
        }),
        ('Rejection', {
            'fields': ('rejected_by', 'rejected_at', 'rejection_reason'),
            'classes': ('collapse',)
        }),
        ('Cancellation', {
            'fields': ('cancelled_at', 'cancellation_reason'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make approval fields readonly after they're set"""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:
            if obj.manager_approver:
                readonly.extend(['manager_approver', 'manager_approved_at', 'manager_comments'])
            if obj.hr_approver:
                readonly.extend(['hr_approver', 'hr_approved_at', 'hr_comments'])
            if obj.final_approver:
                readonly.extend(['final_approver', 'final_approved_at'])
            if obj.rejected_by:
                readonly.extend(['rejected_by', 'rejected_at', 'rejection_reason'])
            if obj.cancelled_at:
                readonly.extend(['cancelled_at', 'cancellation_reason'])
        return readonly


@admin.register(PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    list_display = ['get_name', 'date', 'tenant', 'is_recurring', 'applies_to_all', 'created_at']
    list_filter = ['tenant', 'is_recurring', 'applies_to_all', 'date']
    search_fields = ['name']
    ordering = ['date']
    readonly_fields = ['created_by', 'updated_by', 'created_at', 'updated_at']
    date_hierarchy = 'date'

    fieldsets = (
        ('Holiday Details', {
            'fields': ('tenant', 'name', 'date')
        }),
        ('Settings', {
            'fields': ('is_recurring', 'applies_to_all')
        }),
        ('Audit', {
            'fields': ('created_by', 'updated_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_name(self, obj):
        return obj.get_name('en')
    get_name.short_description = 'Name'

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(LeaveApprovalChain)
class LeaveApprovalChainAdmin(admin.ModelAdmin):
    list_display = ['tenant', 'get_leave_type', 'level', 'approver_role', 'is_required']
    list_filter = ['tenant', 'leave_type', 'approver_role', 'is_required']
    search_fields = ['leave_type__code', 'leave_type__name']
    ordering = ['tenant', 'leave_type', 'level']

    fieldsets = (
        ('Approval Chain', {
            'fields': ('tenant', 'leave_type', 'level', 'approver_role', 'is_required')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_leave_type(self, obj):
        if obj.leave_type:
            return obj.leave_type.get_name('en')
        return 'All Leave Types'
    get_leave_type.short_description = 'Leave Type'

    readonly_fields = ['created_at', 'updated_at']
