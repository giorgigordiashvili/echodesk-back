from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    LeaveSettingsViewSet,
    LeaveTypeViewSet,
    AdminLeaveBalanceViewSet,
    AdminLeaveRequestViewSet,
    PublicHolidayViewSet,
    LeaveApprovalChainViewSet
)
from .views_manager import (
    ManagerLeaveRequestViewSet,
    ManagerTeamBalanceViewSet
)
from .views_employee import (
    EmployeeLeaveRequestViewSet,
    EmployeeLeaveBalanceViewSet,
    EmployeePublicHolidayViewSet,
    EmployeeLeaveTypeViewSet
)

# Admin Router - Full administrative access
admin_router = DefaultRouter()
admin_router.register(r'settings', LeaveSettingsViewSet, basename='leave-settings')
admin_router.register(r'leave-types', LeaveTypeViewSet, basename='leave-type')
admin_router.register(r'leave-requests', AdminLeaveRequestViewSet, basename='admin-leave-request')
admin_router.register(r'leave-balances', AdminLeaveBalanceViewSet, basename='admin-leave-balance')
admin_router.register(r'public-holidays', PublicHolidayViewSet, basename='public-holiday')
admin_router.register(r'approval-chains', LeaveApprovalChainViewSet, basename='approval-chain')

# Manager Router - Team management
manager_router = DefaultRouter()
manager_router.register(r'team-requests', ManagerLeaveRequestViewSet, basename='manager-leave-request')
manager_router.register(r'team-balances', ManagerTeamBalanceViewSet, basename='manager-team-balance')

# Employee Router - Self-service
employee_router = DefaultRouter()
employee_router.register(r'my-requests', EmployeeLeaveRequestViewSet, basename='employee-leave-request')
employee_router.register(r'my-balance', EmployeeLeaveBalanceViewSet, basename='employee-leave-balance')
employee_router.register(r'holidays', EmployeePublicHolidayViewSet, basename='employee-holiday')
employee_router.register(r'leave-types', EmployeeLeaveTypeViewSet, basename='employee-leave-type')

urlpatterns = [
    # Admin endpoints - /api/leave/admin/
    path('admin/', include(admin_router.urls)),

    # Manager endpoints - /api/leave/manager/
    path('manager/', include(manager_router.urls)),

    # Employee endpoints - /api/leave/employee/
    path('employee/', include(employee_router.urls)),
]
