from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from datetime import datetime, timedelta
from decimal import Decimal
import calendar
import django_filters

from .models import (
    WorkSchedule, LeaveType, EmployeeLeaveBalance, LeaveRequest,
    EmployeeWorkSchedule, Holiday, LeaveRequestComment
)
from .serializers import (
    WorkScheduleSerializer, LeaveTypeSerializer, EmployeeLeaveBalanceSerializer,
    LeaveRequestSerializer, LeaveRequestCreateSerializer, LeaveRequestUpdateSerializer,
    LeaveRequestApprovalSerializer, EmployeeWorkScheduleSerializer, HolidaySerializer,
    LeaveRequestCommentSerializer, LeaveBalanceSummarySerializer, EmployeeLeaveReportSerializer
)

User = get_user_model()


class WorkScheduleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing work schedules"""
    queryset = WorkSchedule.objects.all()
    serializer_class = WorkScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['schedule_type', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class LeaveTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing leave types"""
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'is_active', 'requires_approval', 'is_paid']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'category', 'max_days_per_year']
    ordering = ['category', 'name']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by active by default unless specifically requested
        if self.request.query_params.get('include_inactive') != 'true':
            queryset = queryset.filter(is_active=True)
        
        return queryset


class EmployeeLeaveBalanceViewSet(viewsets.ModelViewSet):
    """ViewSet for managing employee leave balances"""
    queryset = EmployeeLeaveBalance.objects.all()
    serializer_class = EmployeeLeaveBalanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['employee', 'leave_type', 'year']
    search_fields = ['employee__first_name', 'employee__last_name', 'employee__email']
    ordering_fields = ['year', 'allocated_days', 'used_days', 'available_days']
    ordering = ['-year', 'leave_type__category']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Regular employees can only see their own balances
        if not user.can_manage_users and not user.is_staff:
            queryset = queryset.filter(employee=user)
        
        return queryset
    
    @action(detail=False, methods=['post'])
    def initialize_year(self, request):
        """Initialize leave balances for employees for a specific year"""
        year = request.data.get('year', timezone.now().year)
        employee_ids = request.data.get('employee_ids', [])
        
        if not request.user.can_manage_users and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        created_balances = []
        
        with transaction.atomic():
            # Get employees to initialize
            if employee_ids:
                employees = User.objects.filter(id__in=employee_ids, is_active=True)
            else:
                employees = User.objects.filter(is_active=True)
            
            # Get all active leave types
            leave_types = LeaveType.objects.filter(is_active=True)
            
            for employee in employees:
                for leave_type in leave_types:
                    balance, created = EmployeeLeaveBalance.objects.get_or_create(
                        employee=employee,
                        leave_type=leave_type,
                        year=year,
                        defaults={
                            'allocated_days': leave_type.max_days_per_year,
                            'used_days': 0,
                            'pending_days': 0,
                            'carried_over_days': 0
                        }
                    )
                    
                    if created:
                        # Handle carry over from previous year if applicable
                        if leave_type.allow_carry_over and year > timezone.now().year - 10:
                            try:
                                prev_balance = EmployeeLeaveBalance.objects.get(
                                    employee=employee,
                                    leave_type=leave_type,
                                    year=year - 1
                                )
                                carry_over = min(
                                    prev_balance.available_days,
                                    leave_type.max_carry_over_days
                                )
                                balance.carried_over_days = max(0, carry_over)
                                balance.save()
                            except EmployeeLeaveBalance.DoesNotExist:
                                pass
                        
                        created_balances.append(balance)
        
        return Response({
            'message': f'Initialized leave balances for {len(created_balances)} employee-leave type combinations',
            'year': year,
            'employees_count': len(employees),
            'leave_types_count': len(leave_types)
        })
    
    @action(detail=False, methods=['get'])
    def my_balances(self, request):
        """Get current user's leave balances"""
        year = request.query_params.get('year', timezone.now().year)
        
        balances = EmployeeLeaveBalance.objects.filter(
            employee=request.user,
            year=year
        ).select_related('leave_type')
        
        serializer = self.get_serializer(balances, many=True)
        return Response(serializer.data)


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for managing leave requests"""
    queryset = LeaveRequest.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'leave_type', 'employee']
    search_fields = ['employee__first_name', 'employee__last_name', 'reason']
    ordering_fields = ['created_at', 'start_date', 'status']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return LeaveRequestCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return LeaveRequestUpdateSerializer
        return LeaveRequestSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'employee', 'leave_type', 'approved_by'
        ).prefetch_related('comments')
        
        user = self.request.user
        
        # Regular employees can only see their own requests
        if not user.can_manage_users and not user.is_staff:
            queryset = queryset.filter(employee=user)
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(end_date__lte=end_date)
        
        return queryset
    
    def perform_create(self, serializer):
        """Set employee to current user when creating"""
        serializer.save(employee=self.request.user)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit a leave request"""
        leave_request = self.get_object()
        
        # Check if user can submit this request
        if leave_request.employee != request.user:
            return Response(
                {'error': 'You can only submit your own requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            leave_request.submit()
            return Response({
                'message': 'Leave request submitted successfully',
                'status': leave_request.status
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def approve_reject(self, request, pk=None):
        """Approve or reject a leave request"""
        leave_request = self.get_object()
        
        # Check permissions
        if not request.user.can_manage_users and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = LeaveRequestApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        action_type = serializer.validated_data['action']
        comments = serializer.validated_data.get('comments', '')
        
        try:
            if action_type == 'approve':
                leave_request.approve(request.user, comments)
                message = 'Leave request approved successfully'
            else:
                leave_request.reject(request.user, comments)
                message = 'Leave request rejected'
            
            return Response({
                'message': message,
                'status': leave_request.status
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a leave request"""
        leave_request = self.get_object()
        
        # Check if user can cancel this request
        if leave_request.employee != request.user and not request.user.can_manage_users:
            return Response(
                {'error': 'You can only cancel your own requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            leave_request.cancel()
            return Response({
                'message': 'Leave request cancelled successfully',
                'status': leave_request.status
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def add_comment(self, request, pk=None):
        """Add a comment to a leave request"""
        leave_request = self.get_object()
        
        # Check permissions
        if (leave_request.employee != request.user and 
            not request.user.can_manage_users and 
            not request.user.is_staff):
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = LeaveRequestCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            leave_request=leave_request,
            author=request.user
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """Get current user's leave requests"""
        requests = self.get_queryset().filter(employee=request.user)
        
        # Apply additional filters
        status_filter = request.query_params.get('status')
        if status_filter:
            requests = requests.filter(status=status_filter)
        
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """Get requests pending approval (for managers)"""
        if not request.user.can_manage_users and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        requests = self.get_queryset().filter(
            status__in=['submitted', 'pending_approval']
        )
        
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def calendar_view(self, request):
        """Get leave requests for calendar view"""
        start_date = request.query_params.get('start')
        end_date = request.query_params.get('end')
        
        if not start_date or not end_date:
            return Response(
                {'error': 'start and end dates are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        requests = self.get_queryset().filter(
            status='approved',
            start_date__lte=end_date,
            end_date__gte=start_date
        )
        
        # Format for calendar
        calendar_events = []
        for req in requests:
            calendar_events.append({
                'id': req.id,
                'title': f"{req.employee.get_full_name()} - {req.leave_type.name}",
                'start': req.start_date.isoformat(),
                'end': (req.end_date + timedelta(days=1)).isoformat(),  # Make end date exclusive
                'color': req.leave_type.color_code,
                'employee': req.employee.get_full_name(),
                'leave_type': req.leave_type.name,
                'duration_type': req.duration_type,
                'total_days': float(req.working_days_count)
            })
        
        return Response(calendar_events)


class EmployeeWorkScheduleFilter(django_filters.FilterSet):
    """Custom filter for EmployeeWorkSchedule to handle employee filtering properly"""
    employee = django_filters.NumberFilter(field_name='employee__id')
    work_schedule = django_filters.NumberFilter(field_name='work_schedule__id')
    is_active = django_filters.BooleanFilter()
    
    class Meta:
        model = EmployeeWorkSchedule
        fields = ['employee', 'work_schedule', 'is_active']


class EmployeeWorkScheduleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing employee work schedules"""
    queryset = EmployeeWorkSchedule.objects.all()
    serializer_class = EmployeeWorkScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = EmployeeWorkScheduleFilter
    search_fields = ['employee__first_name', 'employee__last_name']
    ordering = ['-effective_from']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        
        # Regular employees can only see their own schedules
        if not user.can_manage_users and not user.is_staff:
            queryset = queryset.filter(employee=user)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def my_schedule(self, request):
        """Get current user's active work schedule"""
        try:
            schedule = EmployeeWorkSchedule.objects.get(
                employee=request.user,
                is_active=True
            )
            serializer = self.get_serializer(schedule)
            return Response(serializer.data)
        except EmployeeWorkSchedule.DoesNotExist:
            return Response(
                {'message': 'No active work schedule found'},
                status=status.HTTP_404_NOT_FOUND
            )


class HolidayViewSet(viewsets.ModelViewSet):
    """ViewSet for managing holidays"""
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_recurring']
    search_fields = ['name', 'description']
    ordering_fields = ['date', 'name']
    ordering = ['date']
    
    @action(detail=False, methods=['get'])
    def current_year(self, request):
        """Get holidays for current year"""
        year = request.query_params.get('year', timezone.now().year)
        
        holidays = self.get_queryset().filter(
            Q(date__year=year) | 
            (Q(is_recurring=True) & Q(date__month__gte=1))
        )
        
        serializer = self.get_serializer(holidays, many=True)
        return Response(serializer.data)


class LeaveReportsViewSet(viewsets.ViewSet):
    """ViewSet for leave reports and analytics"""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def employee_summary(self, request):
        """Get leave summary for employees"""
        if not request.user.can_manage_users and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        year = request.query_params.get('year', timezone.now().year)
        department_id = request.query_params.get('department')
        
        # Base queryset
        employees = User.objects.filter(is_active=True)
        
        if department_id:
            employees = employees.filter(department_id=department_id)
        
        report_data = []
        
        for employee in employees:
            # Get leave requests stats
            requests_stats = LeaveRequest.objects.filter(
                employee=employee,
                start_date__year=year
            ).aggregate(
                total_requests=Count('id'),
                approved_requests=Count('id', filter=Q(status='approved')),
                pending_requests=Count('id', filter=Q(status__in=['submitted', 'pending_approval'])),
                rejected_requests=Count('id', filter=Q(status='rejected')),
                total_days_taken=Sum('working_days_count', filter=Q(status='approved'))
            )
            
            # Get leave balances
            balances = EmployeeLeaveBalance.objects.filter(
                employee=employee,
                year=year
            ).select_related('leave_type')
            
            balance_data = []
            for balance in balances:
                balance_data.append({
                    'leave_type_id': balance.leave_type.id,
                    'leave_type_name': balance.leave_type.name,
                    'leave_type_category': balance.leave_type.category,
                    'allocated_days': balance.allocated_days,
                    'used_days': balance.used_days,
                    'pending_days': balance.pending_days,
                    'carried_over_days': balance.carried_over_days,
                    'available_days': balance.available_days,
                    'total_allocated': balance.total_allocated
                })
            
            report_data.append({
                'employee_id': employee.id,
                'employee_name': employee.get_full_name(),
                'employee_email': employee.email,
                'department': employee.department.name if employee.department else None,
                'total_requests': requests_stats['total_requests'] or 0,
                'approved_requests': requests_stats['approved_requests'] or 0,
                'pending_requests': requests_stats['pending_requests'] or 0,
                'rejected_requests': requests_stats['rejected_requests'] or 0,
                'total_days_taken': requests_stats['total_days_taken'] or Decimal('0'),
                'balances': balance_data
            })
        
        serializer = EmployeeLeaveReportSerializer(report_data, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def leave_trends(self, request):
        """Get leave trends and analytics"""
        if not request.user.can_manage_users and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        year = request.query_params.get('year', timezone.now().year)
        
        # Monthly leave trends
        monthly_data = []
        for month in range(1, 13):
            month_requests = LeaveRequest.objects.filter(
                start_date__year=year,
                start_date__month=month,
                status='approved'
            ).aggregate(
                count=Count('id'),
                total_days=Sum('working_days_count')
            )
            
            monthly_data.append({
                'month': month,
                'month_name': calendar.month_name[month],
                'requests_count': month_requests['count'] or 0,
                'total_days': month_requests['total_days'] or Decimal('0')
            })
        
        # Leave type distribution
        leave_type_data = LeaveRequest.objects.filter(
            start_date__year=year,
            status='approved'
        ).values(
            'leave_type__name',
            'leave_type__category'
        ).annotate(
            count=Count('id'),
            total_days=Sum('working_days_count')
        )
        
        # Department wise data
        department_data = LeaveRequest.objects.filter(
            start_date__year=year,
            status='approved'
        ).values(
            'employee__department__name'
        ).annotate(
            count=Count('id'),
            total_days=Sum('working_days_count')
        )
        
        return Response({
            'year': year,
            'monthly_trends': monthly_data,
            'leave_type_distribution': list(leave_type_data),
            'department_wise': list(department_data)
        })
