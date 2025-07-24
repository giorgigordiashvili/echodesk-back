from rest_framework import viewsets, permissions
from .models import CallLog, Client
from .serializers import CallLogSerializer, ClientSerializer


class CallLogViewSet(viewsets.ModelViewSet):
    """ViewSet for CallLog model"""
    queryset = CallLog.objects.all()
    serializer_class = CallLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        # Automatically set the current user as the handler if not specified
        if not serializer.validated_data.get('handled_by'):
            serializer.save(handled_by=self.request.user)
        else:
            serializer.save()


class ClientViewSet(viewsets.ModelViewSet):
    """ViewSet for Client model"""
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]
