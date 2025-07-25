from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import CallLog, Client, SipConfiguration
from .serializers import (
    CallLogSerializer, ClientSerializer, SipConfigurationSerializer,
    SipConfigurationListSerializer, SipConfigurationDetailSerializer,
    CallLogCreateSerializer, CallInitiateSerializer, CallStatusUpdateSerializer
)


class SipConfigurationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing SIP configurations.
    
    Allows tenants to configure their SIP settings for making and receiving calls.
    """
    serializer_class = SipConfigurationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Return configurations for current tenant - tenant schema isolation handles filtering
        if hasattr(self.request, 'tenant'):
            # In tenant schema, all records are for the current tenant
            return SipConfiguration.objects.all()
        else:
            # Fallback for public schema or when tenant is not available
            return SipConfiguration.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'list':
            return SipConfigurationListSerializer
        elif self.action in ['retrieve', 'webrtc_config']:
            return SipConfigurationDetailSerializer
        return SipConfigurationSerializer
    
    @extend_schema(
        summary="Get WebRTC configuration for calling",
        description="Retrieve SIP configuration details needed for WebRTC calling in the frontend",
        responses={
            200: SipConfigurationDetailSerializer,
            404: "SIP configuration not found"
        }
    )
    @action(detail=True, methods=['get'])
    def webrtc_config(self, request, pk=None):
        """Get WebRTC configuration for the frontend"""
        sip_config = self.get_object()
        if not sip_config.is_active:
            return Response(
                {'error': 'SIP configuration is not active'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(sip_config)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Set as default SIP configuration",
        description="Set this SIP configuration as the default for outbound calls",
        responses={200: "Configuration set as default"}
    )
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set this configuration as default"""
        sip_config = self.get_object()
        
        # Remove default from other configs in current tenant
        SipConfiguration.objects.filter(is_default=True).exclude(id=sip_config.id).update(is_default=False)
        
        # Set this as default
        sip_config.is_default = True
        sip_config.save()
        
        return Response({'message': 'Configuration set as default'})
    
    @extend_schema(
        summary="Test SIP configuration",
        description="Test the SIP configuration connectivity",
        responses={
            200: "Configuration test successful",
            400: "Configuration test failed"
        }
    )
    @action(detail=True, methods=['post'])
    def test_connection(self, request, pk=None):
        """Test SIP configuration (placeholder for actual SIP testing)"""
        sip_config = self.get_object()
        
        # In a real implementation, you would test SIP connectivity here
        # For now, just validate that required fields are present
        if not all([sip_config.sip_server, sip_config.username, sip_config.password]):
            return Response(
                {'error': 'Incomplete SIP configuration'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'message': 'SIP configuration test successful',
            'server': sip_config.sip_server,
            'port': sip_config.sip_port
        })


class CallLogViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing call logs with SIP integration.
    
    Handles both inbound and outbound calls, call status updates, and call history.
    """
    serializer_class = CallLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # Return calls for users in current tenant - use request.tenant instead of user.tenant
        if hasattr(self.request, 'tenant'):
            # Filter by tenant through the handled_by user's association with tenant tables
            return CallLog.objects.all()  # In tenant schema, all records are for the current tenant
        else:
            # Fallback for public schema or when tenant is not available
            return CallLog.objects.all()
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CallLogCreateSerializer
        elif self.action == 'initiate_call':
            return CallInitiateSerializer
        elif self.action in ['update_status', 'end_call']:
            return CallStatusUpdateSerializer
        return CallLogSerializer
    
    def perform_create(self, serializer):
        # Automatically set the current user as the handler if not specified
        if not serializer.validated_data.get('handled_by'):
            serializer.save(handled_by=self.request.user)
        else:
            serializer.save()
    
    @extend_schema(
        summary="Initiate an outbound call",
        description="Start a new outbound call using SIP configuration",
        request=CallInitiateSerializer,
        responses={
            201: CallLogSerializer,
            400: "Invalid call data"
        }
    )
    @action(detail=False, methods=['post'])
    def initiate_call(self, request):
        """Initiate an outbound call"""
        serializer = CallInitiateSerializer(data=request.data)
        if serializer.is_valid():
            # Get SIP configuration
            sip_config_id = serializer.validated_data.get('sip_configuration')
            if sip_config_id:
                try:
                    sip_config = SipConfiguration.objects.get(
                        id=sip_config_id,
                        is_active=True
                    )
                except SipConfiguration.DoesNotExist:
                    return Response(
                        {'error': 'Invalid SIP configuration'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                # Use default SIP configuration
                sip_config = SipConfiguration.objects.filter(
                    is_default=True,
                    is_active=True
                ).first()
                
                if not sip_config:
                    return Response(
                        {'error': 'No default SIP configuration found'}, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Create call log
            call_log = CallLog.objects.create(
                caller_number="",  # Will be filled by SIP server
                recipient_number=serializer.validated_data['recipient_number'],
                direction='outbound',
                call_type=serializer.validated_data.get('call_type', 'voice'),
                status='ringing',
                handled_by=request.user,
                sip_configuration=sip_config,
                started_at=timezone.now()
            )
            
            # In a real implementation, you would initiate the actual SIP call here
            # For now, just return the call log
            
            response_serializer = CallLogSerializer(call_log)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Update call status",
        description="Update the status of an ongoing call",
        request=CallStatusUpdateSerializer,
        responses={
            200: CallLogSerializer,
            404: "Call not found"
        }
    )
    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Update call status"""
        call_log = self.get_object()
        serializer = CallStatusUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            # Update call status
            call_log.status = serializer.validated_data['status']
            
            # Set answered_at if call is answered
            if serializer.validated_data['status'] == 'answered' and not call_log.answered_at:
                call_log.answered_at = timezone.now()
            
            # Set ended_at and calculate duration if call ended
            if serializer.validated_data['status'] in ['ended', 'missed', 'failed', 'cancelled']:
                if not call_log.ended_at:
                    call_log.ended_at = timezone.now()
                    if call_log.answered_at:
                        call_log.duration = call_log.ended_at - call_log.answered_at
                    else:
                        call_log.duration = timedelta(seconds=0)
            
            # Update optional fields
            if 'notes' in serializer.validated_data:
                call_log.notes = serializer.validated_data['notes']
            if 'call_quality_score' in serializer.validated_data:
                call_log.call_quality_score = serializer.validated_data['call_quality_score']
            if 'recording_url' in serializer.validated_data:
                call_log.recording_url = serializer.validated_data['recording_url']
            
            call_log.save()
            
            response_serializer = CallLogSerializer(call_log)
            return Response(response_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="End a call",
        description="End an ongoing call and update duration",
        responses={
            200: CallLogSerializer,
            404: "Call not found",
            400: "Call already ended"
        }
    )
    @action(detail=True, methods=['post'])
    def end_call(self, request, pk=None):
        """End an ongoing call"""
        call_log = self.get_object()
        
        if call_log.status in ['ended', 'missed', 'failed', 'cancelled']:
            return Response(
                {'error': 'Call has already ended'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        call_log.status = 'ended'
        call_log.ended_at = timezone.now()
        
        if call_log.answered_at:
            call_log.duration = call_log.ended_at - call_log.answered_at
        else:
            call_log.duration = timedelta(seconds=0)
        
        call_log.save()
        
        serializer = CallLogSerializer(call_log)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Get call statistics",
        description="Get call statistics for the current tenant",
        parameters=[
            OpenApiParameter(
                name='period',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.QUERY,
                description='Time period (today, week, month)',
                enum=['today', 'week', 'month']
            )
        ],
        responses={200: "Call statistics"}
    )
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get call statistics"""
        period = request.query_params.get('period', 'today')
        
        # Calculate date range
        now = timezone.now()
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        else:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        queryset = self.get_queryset().filter(started_at__gte=start_date)
        
        # Calculate statistics
        total_calls = queryset.count()
        answered_calls = queryset.filter(status='answered').count()
        missed_calls = queryset.filter(status='missed').count()
        inbound_calls = queryset.filter(direction='inbound').count()
        outbound_calls = queryset.filter(direction='outbound').count()
        
        # Calculate average duration for answered calls
        answered_durations = queryset.filter(
            status='answered', 
            duration__isnull=False
        ).values_list('duration', flat=True)
        
        avg_duration = None
        if answered_durations:
            total_seconds = sum(d.total_seconds() for d in answered_durations)
            avg_duration = total_seconds / len(answered_durations)
        
        return Response({
            'period': period,
            'total_calls': total_calls,
            'answered_calls': answered_calls,
            'missed_calls': missed_calls,
            'inbound_calls': inbound_calls,
            'outbound_calls': outbound_calls,
            'answer_rate': round((answered_calls / total_calls * 100) if total_calls > 0 else 0, 1),
            'average_duration_seconds': round(avg_duration) if avg_duration else 0
        })


class ClientViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing clients/customers.
    """
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        # In a multi-tenant setup, you might want to filter by tenant
        return Client.objects.all()
    
    @extend_schema(
        summary="Get client call history",
        description="Get all calls associated with this client",
        responses={200: CallLogSerializer(many=True)}
    )
    @action(detail=True, methods=['get'])
    def call_history(self, request, pk=None):
        """Get call history for a specific client"""
        client = self.get_object()
        calls = CallLog.objects.filter(
            client=client
        ).order_by('-started_at')
        
        serializer = CallLogSerializer(calls, many=True)
        return Response(serializer.data)
