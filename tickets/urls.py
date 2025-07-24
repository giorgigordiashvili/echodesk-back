from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TicketViewSet, TagViewSet, TicketCommentViewSet

# Create router and register viewsets
router = DefaultRouter()
router.register(r'tickets', TicketViewSet, basename='ticket')
router.register(r'tags', TagViewSet, basename='tag')
router.register(r'comments', TicketCommentViewSet, basename='ticketcomment')

app_name = 'tickets'

urlpatterns = [
    path('api/', include(router.urls)),
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
