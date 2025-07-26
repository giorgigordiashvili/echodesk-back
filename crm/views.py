from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import CallLog, Client, SipConfiguration, CallEvent, CallRecording
from .serializers import (
    CallLogSerializer, ClientSerializer, SipConfigurationSerializer,
    SipConfigurationListSerializer, SipConfigurationDetailSerializer,
    CallLogCreateSerializer, CallInitiateSerializer, CallStatusUpdateSerializer,
    CallLogDetailSerializer, CallEventSerializer, CallRecordingSerializer
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
        elif self.action == 'retrieve':
            return CallLogDetailSerializer
        return CallLogSerializer
    
    def perform_create(self, serializer):
        # Automatically set the current user as the handler if not specified
        if not serializer.validated_data.get('handled_by'):
            serializer.save(handled_by=self.request.user)
        else:
            serializer.save()
    
    def _create_call_event(self, call_log, event_type, metadata=None, user=None):
        """Helper method to create call events"""
        CallEvent.objects.create(
            call_log=call_log,
            event_type=event_type,
            metadata=metadata or {},
            user=user or self.request.user
        )
    
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
                status='initiated',
                handled_by=request.user,
                sip_configuration=sip_config,
                started_at=timezone.now()
            )
            
            # Create initial call event
            self._create_call_event(
                call_log, 
                'initiated',
                metadata={
                    'sip_config': sip_config.name,
                    'recipient': serializer.validated_data['recipient_number'],
                    'call_type': serializer.validated_data.get('call_type', 'voice')
                }
            )
            
            # In a real implementation, you would initiate the actual SIP call here
            # For now, just return the call log
            
            response_serializer = CallLogSerializer(call_log)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Log an incoming call",
        description="Log an incoming call when it starts ringing",
        request=CallLogCreateSerializer,
        responses={
            201: CallLogSerializer,
            400: "Invalid call data"
        }
    )
    @action(detail=False, methods=['post'])
    def log_incoming_call(self, request):
        """Log an incoming call"""
        # Extract data from request
        caller_number = request.data.get('caller_number', '')
        recipient_number = request.data.get('recipient_number', '')
        sip_call_id = request.data.get('sip_call_id', '')
        
        # Get default SIP configuration
        sip_config = SipConfiguration.objects.filter(
            is_default=True,
            is_active=True
        ).first()
        
        if not sip_config:
            return Response(
                {'error': 'No default SIP configuration found'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create call log for incoming call
        call_log = CallLog.objects.create(
            caller_number=caller_number,
            recipient_number=recipient_number,
            direction='inbound',
            call_type='voice',
            status='ringing',
            handled_by=request.user,
            sip_configuration=sip_config,
            sip_call_id=sip_call_id,
            started_at=timezone.now()
        )
        
        # Create initial call event
        self._create_call_event(
            call_log,
            'ringing',
            metadata={
                'caller': caller_number,
                'recipient': recipient_number,
                'sip_call_id': sip_call_id
            }
        )
        
        response_serializer = CallLogSerializer(call_log)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
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
            old_status = call_log.status
            new_status = serializer.validated_data['status']
            
            # Update call status
            call_log.status = new_status
            
            # Set answered_at if call is answered
            if new_status == 'answered' and not call_log.answered_at:
                call_log.answered_at = timezone.now()
            
            # Set ended_at and calculate duration if call ended
            if new_status in ['ended', 'missed', 'failed', 'cancelled']:
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
            
            # Create call event for status change
            event_metadata = {
                'old_status': old_status,
                'new_status': new_status
            }
            if 'notes' in serializer.validated_data:
                event_metadata['notes'] = serializer.validated_data['notes']
            if 'call_quality_score' in serializer.validated_data:
                event_metadata['quality_score'] = serializer.validated_data['call_quality_score']
            
            self._create_call_event(call_log, new_status, metadata=event_metadata)
            
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
        
        # Create call event for call end
        self._create_call_event(
            call_log,
            'ended',
            metadata={
                'duration_seconds': call_log.duration.total_seconds() if call_log.duration else 0,
                'ended_by': 'user'
            }
        )
        
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
    
    @extend_schema(
        summary="Add call event",
        description="Add a specific event to a call (hold, mute, etc.)",
        request=CallEventSerializer,
        responses={201: CallEventSerializer}
    )
    @action(detail=True, methods=['post'])
    def add_event(self, request, pk=None):
        """Add an event to a call"""
        call_log = self.get_object()
        
        event_data = request.data.copy()
        event_data['call_log'] = call_log.id
        
        serializer = CallEventSerializer(data=event_data)
        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(
        summary="Start call recording",
        description="Start recording for an active call",
        responses={
            201: CallRecordingSerializer,
            400: "Recording already exists or call not active"
        }
    )
    @action(detail=True, methods=['post'])
    def start_recording(self, request, pk=None):
        """Start recording for a call"""
        call_log = self.get_object()
        
        # Check if call is active
        if call_log.status not in ['answered', 'on_hold']:
            return Response(
                {'error': 'Call must be answered to start recording'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if recording already exists
        if hasattr(call_log, 'recording'):
            return Response(
                {'error': 'Recording already exists for this call'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create recording record
        recording = CallRecording.objects.create(
            call_log=call_log,
            status='recording',
            started_at=timezone.now()
        )
        
        # Create call event
        self._create_call_event(
            call_log,
            'recording_started',
            metadata={'recording_id': str(recording.recording_id)}
        )
        
        # Update call status to indicate recording
        call_log.status = 'recording'
        call_log.save()
        
        serializer = CallRecordingSerializer(recording)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @extend_schema(
        summary="Stop call recording",
        description="Stop recording for an active call",
        responses={
            200: CallRecordingSerializer,
            400: "No active recording found"
        }
    )
    @action(detail=True, methods=['post'])
    def stop_recording(self, request, pk=None):
        """Stop recording for a call"""
        call_log = self.get_object()
        
        # Check if recording exists
        if not hasattr(call_log, 'recording'):
            return Response(
                {'error': 'No recording found for this call'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        recording = call_log.recording
        if recording.status != 'recording':
            return Response(
                {'error': 'Recording is not active'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Stop recording
        recording.status = 'processing'
        recording.completed_at = timezone.now()
        if recording.started_at:
            recording.duration = recording.completed_at - recording.started_at
        recording.save()
        
        # Create call event
        self._create_call_event(
            call_log,
            'recording_stopped',
            metadata={
                'recording_id': str(recording.recording_id),
                'duration_seconds': recording.duration.total_seconds() if recording.duration else 0
            }
        )
        
        # Update call status back to answered
        call_log.status = 'answered'
        call_log.save()
        
        serializer = CallRecordingSerializer(recording)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Transfer call",
        description="Transfer an active call to another number",
        responses={200: CallLogSerializer}
    )
    @action(detail=True, methods=['post'])
    def transfer_call(self, request, pk=None):
        """Transfer call to another number"""
        call_log = self.get_object()
        transfer_to = request.data.get('transfer_to')
        
        if not transfer_to:
            return Response(
                {'error': 'transfer_to number is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if call_log.status not in ['answered', 'on_hold']:
            return Response(
                {'error': 'Call must be answered to transfer'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create transfer events
        self._create_call_event(
            call_log,
            'transfer_initiated',
            metadata={'transfer_to': transfer_to}
        )
        
        # In a real implementation, you would initiate the SIP transfer here
        # For now, just update the status and create completion event
        
        call_log.status = 'transferred'
        call_log.ended_at = timezone.now()
        if call_log.answered_at:
            call_log.duration = call_log.ended_at - call_log.answered_at
        call_log.save()
        
        self._create_call_event(
            call_log,
            'transfer_completed',
            metadata={'transfer_to': transfer_to}
        )
        
        serializer = CallLogSerializer(call_log)
        return Response(serializer.data)
    
    @extend_schema(
        summary="Hold/Unhold call",
        description="Put call on hold or resume from hold",
        responses={200: CallLogSerializer}
    )
    @action(detail=True, methods=['post'])
    def toggle_hold(self, request, pk=None):
        """Toggle hold status for a call"""
        call_log = self.get_object()
        
        if call_log.status == 'answered':
            new_status = 'on_hold'
            event_type = 'hold'
        elif call_log.status == 'on_hold':
            new_status = 'answered'
            event_type = 'unhold'
        else:
            return Response(
                {'error': 'Call must be answered or on hold'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        call_log.status = new_status
        call_log.save()
        
        self._create_call_event(call_log, event_type)
        
        serializer = CallLogSerializer(call_log)
        return Response(serializer.data)


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


@extend_schema(
    summary="SIP Call Event Webhook",
    description="Webhook endpoint for receiving call events from SIP server",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "enum": ["call_initiated", "call_ringing", "call_answered", "call_ended", "call_failed"]},
                "call_id": {"type": "string"},
                "sip_call_id": {"type": "string"},
                "caller_number": {"type": "string"},
                "recipient_number": {"type": "string"},
                "timestamp": {"type": "string", "format": "date-time"},
                "metadata": {"type": "object"}
            },
            "required": ["event_type", "sip_call_id"]
        }
    },
    responses={200: "Event processed successfully"}
)
@api_view(['POST'])
@permission_classes([])
@csrf_exempt
def sip_webhook(request):
    """
    Webhook endpoint for receiving SIP call events
    This endpoint should be called by your SIP server to update call status
    """
    try:
        data = request.data
        event_type = data.get('event_type')
        sip_call_id = data.get('sip_call_id')
        caller_number = data.get('caller_number', '')
        recipient_number = data.get('recipient_number', '')
        metadata = data.get('metadata', {})
        
        if not event_type or not sip_call_id:
            return Response(
                {'error': 'event_type and sip_call_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Map SIP events to our call statuses
        event_status_map = {
            'call_initiated': 'initiated',
            'call_ringing': 'ringing',
            'call_answered': 'answered',
            'call_ended': 'ended',
            'call_failed': 'failed',
            'call_busy': 'busy',
            'call_no_answer': 'no_answer'
        }
        
        call_status = event_status_map.get(event_type, 'ringing')
        
        # Try to find existing call log by SIP call ID
        try:
            call_log = CallLog.objects.get(sip_call_id=sip_call_id)
            
            # Update existing call
            old_status = call_log.status
            call_log.status = call_status
            
            if call_status == 'answered' and not call_log.answered_at:
                call_log.answered_at = timezone.now()
            elif call_status in ['ended', 'failed', 'busy', 'no_answer']:
                if not call_log.ended_at:
                    call_log.ended_at = timezone.now()
                    if call_log.answered_at:
                        call_log.duration = call_log.ended_at - call_log.answered_at
                    else:
                        call_log.duration = timedelta(seconds=0)
            
            call_log.save()
            
            # Create call event
            CallEvent.objects.create(
                call_log=call_log,
                event_type=event_type.replace('call_', ''),
                metadata={
                    'sip_event': True,
                    'old_status': old_status,
                    'new_status': call_status,
                    **metadata
                }
            )
            
        except CallLog.DoesNotExist:
            # Create new call log for incoming calls
            if event_type in ['call_initiated', 'call_ringing']:
                # Get default SIP configuration
                sip_config = SipConfiguration.objects.filter(
                    is_default=True,
                    is_active=True
                ).first()
                
                call_log = CallLog.objects.create(
                    caller_number=caller_number,
                    recipient_number=recipient_number,
                    direction='inbound' if caller_number != recipient_number else 'outbound',
                    status=call_status,
                    sip_call_id=sip_call_id,
                    sip_configuration=sip_config,
                    started_at=timezone.now()
                )
                
                # Create initial event
                CallEvent.objects.create(
                    call_log=call_log,
                    event_type=event_type.replace('call_', ''),
                    metadata={
                        'sip_event': True,
                        'caller': caller_number,
                        'recipient': recipient_number,
                        **metadata
                    }
                )
            else:
                return Response(
                    {'error': f'Call not found for sip_call_id: {sip_call_id}'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response({
            'message': 'Event processed successfully',
            'call_id': str(call_log.call_id),
            'status': call_log.status
        })
        
    except Exception as e:
        return Response(
            {'error': f'Error processing webhook: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    summary="Call Recording Webhook",
    description="Webhook endpoint for receiving call recording updates",
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "call_id": {"type": "string"},
                "recording_id": {"type": "string"},
                "status": {"type": "string", "enum": ["started", "completed", "failed"]},
                "file_url": {"type": "string"},
                "file_size": {"type": "integer"},
                "duration": {"type": "integer", "description": "Duration in seconds"},
                "format": {"type": "string"}
            },
            "required": ["call_id", "status"]
        }
    },
    responses={200: "Recording update processed successfully"}
)
@api_view(['POST'])
@permission_classes([])
@csrf_exempt
def recording_webhook(request):
    """
    Webhook endpoint for receiving call recording updates
    """
    try:
        data = request.data
        call_id = data.get('call_id')
        recording_status = data.get('status')
        file_url = data.get('file_url', '')
        file_size = data.get('file_size')
        duration_seconds = data.get('duration')
        format_type = data.get('format', 'wav')
        
        if not call_id or not recording_status:
            return Response(
                {'error': 'call_id and status are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find call log
        try:
            call_log = CallLog.objects.get(call_id=call_id)
        except CallLog.DoesNotExist:
            return Response(
                {'error': f'Call not found for call_id: {call_id}'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get or create recording
        recording, created = CallRecording.objects.get_or_create(
            call_log=call_log,
            defaults={
                'status': 'pending',
                'format': format_type
            }
        )
        
        # Update recording
        recording.status = recording_status
        if file_url:
            recording.file_url = file_url
        if file_size:
            recording.file_size = file_size
        if duration_seconds:
            recording.duration = timedelta(seconds=duration_seconds)
        
        if recording_status == 'started':
            recording.started_at = timezone.now()
        elif recording_status == 'completed':
            recording.completed_at = timezone.now()
            
        recording.save()
        
        # Create call event
        event_type = f'recording_{recording_status}'
        CallEvent.objects.create(
            call_log=call_log,
            event_type=event_type,
            metadata={
                'recording_webhook': True,
                'recording_id': str(recording.recording_id),
                'file_url': file_url,
                'file_size': file_size,
                'duration_seconds': duration_seconds
            }
        )
        
        return Response({
            'message': 'Recording update processed successfully',
            'recording_id': str(recording.recording_id),
            'status': recording.status
        })
        
    except Exception as e:
        return Response(
            {'error': f'Error processing recording webhook: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
