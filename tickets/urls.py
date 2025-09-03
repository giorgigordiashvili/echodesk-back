from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TicketViewSet, TagViewSet, TicketCommentViewSet, TicketColumnViewSet, 
    SubTicketViewSet, ChecklistItemViewSet, TicketAssignmentViewSet, SubTicketAssignmentViewSet,
    TicketTimeLogViewSet, BoardViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'boards', BoardViewSet, basename='board')
router.register(r'columns', TicketColumnViewSet, basename='ticketcolumn')
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'comments', TicketCommentViewSet, basename='ticketcomment')
router.register(r'sub-tickets', SubTicketViewSet, basename='subticket')
router.register(r'checklist-items', ChecklistItemViewSet, basename='checklistitem')
router.register(r'time-logs', TicketTimeLogViewSet, basename='tickettimelog')

app_name = 'tickets'

urlpatterns = [
    path('api/', include(router.urls)),
    # Manual nested URLs for assignments
    path('api/tickets/<int:ticket_pk>/assignments/', TicketAssignmentViewSet.as_view({'get': 'list', 'post': 'create'}), name='ticket-assignments-list'),
    path('api/tickets/<int:ticket_pk>/assignments/<int:pk>/', TicketAssignmentViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='ticket-assignments-detail'),
    path('api/tickets/<int:ticket_pk>/assignments/bulk_assign/', TicketAssignmentViewSet.as_view({'post': 'bulk_assign'}), name='ticket-assignments-bulk-assign'),
    path('api/tickets/<int:ticket_pk>/assignments/bulk_unassign/', TicketAssignmentViewSet.as_view({'delete': 'bulk_unassign'}), name='ticket-assignments-bulk-unassign'),
    
    path('api/sub-tickets/<int:sub_ticket_pk>/assignments/', SubTicketAssignmentViewSet.as_view({'get': 'list', 'post': 'create'}), name='sub-ticket-assignments-list'),
    path('api/sub-tickets/<int:sub_ticket_pk>/assignments/<int:pk>/', SubTicketAssignmentViewSet.as_view({'get': 'retrieve', 'put': 'update', 'patch': 'partial_update', 'delete': 'destroy'}), name='sub-ticket-assignments-detail'),
    path('api/sub-tickets/<int:sub_ticket_pk>/assignments/bulk_assign/', SubTicketAssignmentViewSet.as_view({'post': 'bulk_assign'}), name='sub-ticket-assignments-bulk-assign'),
    path('api/sub-tickets/<int:sub_ticket_pk>/assignments/bulk_unassign/', SubTicketAssignmentViewSet.as_view({'delete': 'bulk_unassign'}), name='sub-ticket-assignments-bulk-unassign'),
]

# Example URLConf for including in main router:
# In your main urls.py, include this app like:
# path('tickets/', include('tickets.urls')),
#
# This will create the following endpoints:
# - GET/POST /tickets/api/tickets/ - List/Create tickets
# - GET/PUT/PATCH/DELETE /tickets/api/tickets/{id}/ - Retrieve/Update/Delete ticket
# - POST /tickets/api/tickets/{id}/add_comment/ - Add comment to ticket
# - GET /tickets/api/tickets/{id}/comments/ - Get ticket comments
# - GET /tickets/api/tickets/my_tickets/ - Get current user's tickets
# - GET /tickets/api/tickets/assigned_to_me/ - Get tickets assigned to current user
# - PATCH /tickets/api/tickets/{id}/assign/ - Assign ticket (staff only)
# - GET/POST /tickets/api/tags/ - List/Create tags
# - GET/PUT/PATCH/DELETE /tickets/api/tags/{id}/ - Retrieve/Update/Delete tag
# - GET/POST /tickets/api/comments/ - List/Create comments
# - GET/PUT/PATCH/DELETE /tickets/api/comments/{id}/ - Retrieve/Update/Delete comment
