from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WorkScheduleViewSet, LeaveTypeViewSet, EmployeeLeaveBalanceViewSet,
    LeaveRequestViewSet, EmployeeWorkScheduleViewSet, HolidayViewSet,
    LeaveReportsViewSet
)

router = DefaultRouter()
router.register(r'work-schedules', WorkScheduleViewSet)
router.register(r'leave-types', LeaveTypeViewSet)
router.register(r'leave-balances', EmployeeLeaveBalanceViewSet)
router.register(r'leave-requests', LeaveRequestViewSet)
router.register(r'employee-schedules', EmployeeWorkScheduleViewSet)
router.register(r'holidays', HolidayViewSet)
router.register(r'reports', LeaveReportsViewSet, basename='leave-reports')

urlpatterns = [
    path('api/hr/', include(router.urls)),
]
