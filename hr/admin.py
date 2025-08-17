from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    WorkSchedule, LeaveType, EmployeeLeaveBalance, LeaveRequest,
    EmployeeWorkSchedule, Holiday, LeaveRequestComment
)


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ('name', 'schedule_type', 'hours_per_week', 'working_days_display', 'is_active')
    list_filter = ('schedule_type', 'is_active')
    search_fields = ('name', 'description')
    ordering = ('name',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'schedule_type', 'is_active')
        }),
        ('Working Hours', {
            'fields': ('hours_per_day', 'hours_per_week', 'start_time', 'end_time', 'break_duration_minutes')
        }),
        ('Working Days', {
            'fields': (
                ('monday', 'tuesday', 'wednesday', 'thursday'),
                ('friday', 'saturday', 'sunday')
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def working_days_display(self, obj):
        days = obj.get_working_days_list()
        return ', '.join(days[:3]) + ('...' if len(days) > 3 else '')
    working_days_display.short_description = 'Working Days'


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'max_days_per_year', 'requires_approval', 'is_paid', 'is_active')
    list_filter = ('category', 'requires_approval', 'is_paid', 'is_active', 'allow_carry_over')
    search_fields = ('name', 'description')
    ordering = ('category', 'name')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'category', 'color_code', 'is_active')
        }),
        ('Leave Allocation', {
            'fields': ('max_days_per_year', 'allow_carry_over', 'max_carry_over_days')
        }),
        ('Request Settings', {
            'fields': (
                'requires_approval', 'min_notice_days', 'max_consecutive_days',
                'requires_medical_certificate', 'medical_certificate_threshold_days'
            )
        }),
        ('Eligibility', {
            'fields': (
                'minimum_service_months', 'available_to_probationary', 'gender_specific'
            )
        }),
        ('Payment', {
            'fields': ('is_paid',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def color_preview(self, obj):
        return format_html(
            '<div style="width: 20px; height: 20px; background-color: {}; border: 1px solid #ccc;"></div>',
            obj.color_code
        )
    color_preview.short_description = 'Color'


@admin.register(EmployeeLeaveBalance)
class EmployeeLeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'year', 'allocated_days', 'used_days', 'pending_days', 'available_days')
    list_filter = ('year', 'leave_type__category', 'leave_type')
    search_fields = ('employee__first_name', 'employee__last_name', 'employee__email')
    ordering = ('-year', 'employee__last_name', 'leave_type__name')
    
    fieldsets = (
        ('Employee & Leave Type', {
            'fields': ('employee', 'leave_type', 'year')
        }),
        ('Balance Details', {
            'fields': ('allocated_days', 'used_days', 'pending_days', 'carried_over_days')
        }),
        ('Calculated Fields', {
            'fields': ('available_days_display', 'total_allocated_display'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'updated_at', 'available_days_display', 'total_allocated_display')
    
    def available_days_display(self, obj):
        return obj.available_days
    available_days_display.short_description = 'Available Days'
    
    def total_allocated_display(self, obj):
        return obj.total_allocated
    total_allocated_display.short_description = 'Total Allocated'
    
    actions = ['initialize_current_year_balances']
    
    def initialize_current_year_balances(self, request, queryset):
        # This would initialize balances for selected employees
        pass
    initialize_current_year_balances.short_description = "Initialize current year balances"


class LeaveRequestCommentInline(admin.TabularInline):
    model = LeaveRequestComment
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('author', 'comment', 'is_internal', 'created_at')


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = (
        'employee', 'leave_type', 'start_date', 'end_date', 'working_days_count',
        'status', 'approved_by', 'submitted_at'
    )
    list_filter = (
        'status', 'leave_type__category', 'leave_type', 'duration_type',
        'start_date', 'submitted_at'
    )
    search_fields = (
        'employee__first_name', 'employee__last_name', 'employee__email',
        'reason', 'approval_comments'
    )
    ordering = ('-created_at',)
    
    fieldsets = (
        ('Request Details', {
            'fields': (
                'employee', 'leave_type', 'start_date', 'end_date',
                'duration_type', 'start_time', 'end_time'
            )
        }),
        ('Calculated Information', {
            'fields': ('total_days', 'working_days_count'),
            'classes': ('collapse',)
        }),
        ('Request Information', {
            'fields': ('reason', 'emergency_contact', 'handover_notes')
        }),
        ('Status & Approval', {
            'fields': (
                'status', 'approved_by', 'approval_date',
                'approval_comments', 'submitted_at'
            )
        }),
        ('Documents', {
            'fields': ('medical_certificate', 'supporting_documents'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = (
        'total_days', 'working_days_count', 'submitted_at',
        'created_at', 'updated_at'
    )
    
    inlines = [LeaveRequestCommentInline]
    
    actions = ['approve_requests', 'reject_requests']
    
    def approve_requests(self, request, queryset):
        count = 0
        for leave_request in queryset.filter(status__in=['submitted', 'pending_approval']):
            try:
                leave_request.approve(request.user, 'Bulk approved from admin')
                count += 1
            except:
                pass
        self.message_user(request, f'{count} leave requests approved.')
    approve_requests.short_description = "Approve selected requests"
    
    def reject_requests(self, request, queryset):
        count = 0
        for leave_request in queryset.filter(status__in=['submitted', 'pending_approval']):
            try:
                leave_request.reject(request.user, 'Bulk rejected from admin')
                count += 1
            except:
                pass
        self.message_user(request, f'{count} leave requests rejected.')
    reject_requests.short_description = "Reject selected requests"


@admin.register(EmployeeWorkSchedule)
class EmployeeWorkScheduleAdmin(admin.ModelAdmin):
    list_display = ('employee', 'work_schedule', 'effective_from', 'effective_to', 'is_active')
    list_filter = ('work_schedule', 'is_active', 'effective_from')
    search_fields = ('employee__first_name', 'employee__last_name', 'employee__email')
    ordering = ('-effective_from', 'employee__last_name')
    
    fieldsets = (
        ('Assignment', {
            'fields': ('employee', 'work_schedule')
        }),
        ('Effective Period', {
            'fields': ('effective_from', 'effective_to', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'is_recurring', 'description')
    list_filter = ('is_recurring', 'date')
    search_fields = ('name', 'description')
    ordering = ('date',)
    
    fieldsets = (
        ('Holiday Information', {
            'fields': ('name', 'date', 'is_recurring', 'description')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )
    
    readonly_fields = ('created_at',)


@admin.register(LeaveRequestComment)
class LeaveRequestCommentAdmin(admin.ModelAdmin):
    list_display = ('leave_request', 'author', 'comment_preview', 'is_internal', 'created_at')
    list_filter = ('is_internal', 'created_at')
    search_fields = ('comment', 'author__first_name', 'author__last_name')
    ordering = ('-created_at',)
    
    readonly_fields = ('created_at',)
    
    def comment_preview(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment
    comment_preview.short_description = 'Comment'
