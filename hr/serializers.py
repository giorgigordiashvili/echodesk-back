from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (
    WorkSchedule, LeaveType, EmployeeLeaveBalance, LeaveRequest,
    EmployeeWorkSchedule, Holiday, LeaveRequestComment
)

User = get_user_model()


class WorkScheduleSerializer(serializers.ModelSerializer):
    working_days_count = serializers.ReadOnlyField()
    working_days_list = serializers.ReadOnlyField(source='get_working_days_list')
    
    class Meta:
        model = WorkSchedule
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class EmployeeLeaveBalanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    leave_type_category = serializers.CharField(source='leave_type.category', read_only=True)
    available_days = serializers.ReadOnlyField()
    total_allocated = serializers.ReadOnlyField()
    
    class Meta:
        model = EmployeeLeaveBalance
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class EmployeeWorkScheduleSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)
    work_schedule_name = serializers.CharField(source='work_schedule.name', read_only=True)
    work_schedule_details = WorkScheduleSerializer(source='work_schedule', read_only=True)
    
    class Meta:
        model = EmployeeWorkSchedule
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class LeaveRequestCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.get_full_name', read_only=True)
    
    class Meta:
        model = LeaveRequestComment
        fields = '__all__'
        read_only_fields = ('created_at',)


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.get_full_name', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    leave_type_category = serializers.CharField(source='leave_type.category', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.get_full_name', read_only=True)
    comments = LeaveRequestCommentSerializer(many=True, read_only=True)
    can_submit_info = serializers.SerializerMethodField()
    
    class Meta:
        model = LeaveRequest
        fields = '__all__'
        read_only_fields = (
            'total_days', 'working_days_count', 'approved_by', 'approval_date',
            'submitted_at', 'created_at', 'updated_at'
        )
    
    def get_can_submit_info(self, obj):
        """Get information about whether request can be submitted"""
        if obj.status == 'draft':
            can_submit, message = obj.can_be_submitted()
            return {'can_submit': can_submit, 'message': message}
        return {'can_submit': False, 'message': 'Not in draft status'}
    
    def validate(self, data):
        """Validate leave request data"""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        duration_type = data.get('duration_type')
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if start_date and end_date:
            if start_date > end_date:
                raise serializers.ValidationError("Start date cannot be after end date")
            
            # Check if requesting leave for past dates (except emergency)
            leave_type = data.get('leave_type')
            if leave_type and start_date < timezone.now().date():
                if leave_type.category != 'emergency':
                    raise serializers.ValidationError("Cannot request leave for past dates")
        
        # Validate time fields for hourly requests
        if duration_type == 'hours':
            if not start_time or not end_time:
                raise serializers.ValidationError({
                    'start_time': 'Start time is required for hourly requests',
                    'end_time': 'End time is required for hourly requests'
                })
            if start_time >= end_time:
                raise serializers.ValidationError("Start time must be before end time")
        
        return data
    
    def create(self, validated_data):
        # Set employee to current user if not provided
        if 'employee' not in validated_data:
            validated_data['employee'] = self.context['request'].user
        
        return super().create(validated_data)


class LeaveRequestCreateSerializer(LeaveRequestSerializer):
    """Serializer for creating leave requests with limited fields"""
    
    class Meta(LeaveRequestSerializer.Meta):
        fields = [
            'leave_type', 'start_date', 'end_date', 'duration_type',
            'start_time', 'end_time', 'reason', 'emergency_contact',
            'handover_notes', 'medical_certificate', 'supporting_documents'
        ]


class LeaveRequestUpdateSerializer(LeaveRequestSerializer):
    """Serializer for updating leave requests (limited fields when submitted)"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # If the request is already submitted, only allow updating certain fields
        if self.instance and self.instance.status not in ['draft']:
            allowed_fields = ['reason', 'emergency_contact', 'handover_notes', 
                            'medical_certificate', 'supporting_documents']
            
            # Remove fields that can't be updated after submission
            for field_name in list(self.fields.keys()):
                if field_name not in allowed_fields:
                    self.fields.pop(field_name)


class LeaveRequestApprovalSerializer(serializers.Serializer):
    """Serializer for approving/rejecting leave requests"""
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    comments = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        if data['action'] == 'reject' and not data.get('comments'):
            raise serializers.ValidationError("Comments are required when rejecting a request")
        return data


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = '__all__'
        read_only_fields = ('created_at',)


class LeaveRequestStatusSerializer(serializers.Serializer):
    """Serializer for updating leave request status"""
    status = serializers.ChoiceField(choices=LeaveRequest.STATUS_CHOICES)
    comments = serializers.CharField(required=False, allow_blank=True)


class LeaveBalanceSummarySerializer(serializers.Serializer):
    """Serializer for leave balance summary"""
    leave_type_id = serializers.IntegerField()
    leave_type_name = serializers.CharField()
    leave_type_category = serializers.CharField()
    allocated_days = serializers.DecimalField(max_digits=5, decimal_places=1)
    used_days = serializers.DecimalField(max_digits=5, decimal_places=1)
    pending_days = serializers.DecimalField(max_digits=5, decimal_places=1)
    carried_over_days = serializers.DecimalField(max_digits=5, decimal_places=1)
    available_days = serializers.DecimalField(max_digits=5, decimal_places=1)
    total_allocated = serializers.DecimalField(max_digits=5, decimal_places=1)


class EmployeeLeaveReportSerializer(serializers.Serializer):
    """Serializer for employee leave reports"""
    employee_id = serializers.IntegerField()
    employee_name = serializers.CharField()
    employee_email = serializers.CharField()
    department = serializers.CharField(allow_null=True)
    total_requests = serializers.IntegerField()
    approved_requests = serializers.IntegerField()
    pending_requests = serializers.IntegerField()
    rejected_requests = serializers.IntegerField()
    total_days_taken = serializers.DecimalField(max_digits=7, decimal_places=1)
    balances = LeaveBalanceSummarySerializer(many=True)
