# Call Logging API Documentation

This document describes the enhanced call logging functionality for incoming and outgoing calls.

## Overview

The call logging system provides comprehensive tracking of phone calls with the following features:

- **Call Management**: Initiate, answer, hold, transfer, and end calls
- **Event Tracking**: Detailed logging of all call events (ringing, answered, hold, etc.)
- **Recording Management**: Start/stop recording with file management
- **Statistics**: Call analytics and reporting
- **Webhook Integration**: Real-time updates from SIP servers

## Models

### CallLog
Main model for tracking phone calls with enhanced status tracking:
- **Status Options**: initiated, ringing, answered, missed, busy, no_answer, failed, cancelled, transferred, ended, recording, on_hold
- **Directions**: inbound, outbound
- **Call Types**: voice, video, conference

### CallEvent
Tracks detailed events during a call:
- **Event Types**: initiated, ringing, answered, hold, unhold, transfer_initiated, transfer_completed, recording_started, recording_stopped, muted, unmuted, dtmf, quality_change, ended, failed, error

### CallRecording
Manages call recordings separately:
- **Status Options**: pending, recording, processing, completed, failed, deleted
- **File Management**: local paths, external URLs, file sizes
- **Transcription**: AI-generated transcripts with confidence scores

## API Endpoints

### Core Call Management

#### 1. List/Create Calls
- **GET /api/call-logs/** - List all calls
- **POST /api/call-logs/** - Create a new call log

#### 2. Call Details
- **GET /api/call-logs/{id}/** - Get detailed call information with events and recording

#### 3. Initiate Outbound Call
```http
POST /api/call-logs/initiate_call/
{
  "recipient_number": "+1234567890",
  "call_type": "voice",
  "sip_configuration": 1  // optional
}
```

#### 4. Log Incoming Call
```http
POST /api/call-logs/log_incoming_call/
{
  "caller_number": "+1234567890",
  "recipient_number": "+0987654321",
  "sip_call_id": "unique-sip-id"
}
```

#### 5. Update Call Status
```http
PATCH /api/call-logs/{id}/update_status/
{
  "status": "answered",
  "notes": "Customer inquiry about billing",
  "call_quality_score": 4.5
}
```

#### 6. End Call
```http
POST /api/call-logs/{id}/end_call/
```

### Advanced Call Features

#### 7. Add Call Event
```http
POST /api/call-logs/{id}/add_event/
{
  "event_type": "muted",
  "metadata": {
    "reason": "background_noise"
  }
}
```

#### 8. Start Recording
```http
POST /api/call-logs/{id}/start_recording/
```

#### 9. Stop Recording
```http
POST /api/call-logs/{id}/stop_recording/
```

#### 10. Transfer Call
```http
POST /api/call-logs/{id}/transfer_call/
{
  "transfer_to": "+1234567890"
}
```

#### 11. Hold/Unhold Call
```http
POST /api/call-logs/{id}/toggle_hold/
```

### Statistics and Reporting

#### 12. Call Statistics
```http
GET /api/call-logs/statistics/?period=today
GET /api/call-logs/statistics/?period=week
GET /api/call-logs/statistics/?period=month
```

Response:
```json
{
  "period": "today",
  "total_calls": 45,
  "answered_calls": 38,
  "missed_calls": 7,
  "inbound_calls": 25,
  "outbound_calls": 20,
  "answer_rate": 84.4,
  "average_duration_seconds": 185
}
```

### SIP Configuration

#### 13. SIP Configurations
- **GET /api/sip-configurations/** - List SIP configs
- **POST /api/sip-configurations/** - Create SIP config
- **GET /api/sip-configurations/{id}/webrtc_config/** - Get WebRTC config for frontend
- **POST /api/sip-configurations/{id}/set_default/** - Set as default config
- **POST /api/sip-configurations/{id}/test_connection/** - Test SIP connectivity

### Client Management

#### 14. Clients
- **GET /api/clients/** - List clients
- **POST /api/clients/** - Create client
- **GET /api/clients/{id}/call_history/** - Get client's call history

### Webhook Endpoints

#### 15. SIP Events Webhook
```http
POST /api/webhooks/sip/
{
  "event_type": "call_answered",
  "sip_call_id": "unique-sip-id",
  "caller_number": "+1234567890",
  "recipient_number": "+0987654321",
  "timestamp": "2025-07-26T10:30:00Z",
  "metadata": {
    "server": "sip1.example.com",
    "codec": "G.711"
  }
}
```

#### 16. Recording Webhook
```http
POST /api/webhooks/recording/
{
  "call_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "file_url": "https://recordings.example.com/call123.wav",
  "file_size": 2048576,
  "duration": 185,
  "format": "wav"
}
```

## Event Flow Examples

### Outbound Call Flow
1. **POST /api/call-logs/initiate_call/** - Start call
2. **Webhook: call_ringing** - SIP server confirms ringing
3. **Webhook: call_answered** - Call is answered
4. **POST /api/call-logs/{id}/start_recording/** - Start recording (optional)
5. **POST /api/call-logs/{id}/add_event/** - Add events during call
6. **POST /api/call-logs/{id}/end_call/** - End call

### Inbound Call Flow
1. **Webhook: call_initiated** - SIP server initiates call
2. **POST /api/call-logs/log_incoming_call/** - Log incoming call
3. **PATCH /api/call-logs/{id}/update_status/** - Answer call
4. **POST /api/call-logs/{id}/start_recording/** - Start recording (optional)
5. **POST /api/call-logs/{id}/end_call/** - End call

## Testing

Use the management command to create test data:

```bash
# Create 10 test calls with events and recordings
python manage.py test_call_logging --count 10

# Clean up test data and create new ones
python manage.py test_call_logging --count 5 --cleanup
```

## Integration Notes

### SIP Server Integration
- Configure your SIP server to send webhooks to `/api/webhooks/sip/`
- Ensure proper authentication and network access
- Map your SIP events to the supported event types

### Recording Integration
- Configure your recording system to send status updates to `/api/webhooks/recording/`
- Ensure file URLs are accessible from your application
- Consider implementing file cleanup policies

### Frontend Integration
- Use WebSocket connections for real-time call status updates
- Implement call controls using the provided API endpoints
- Handle call events for UI state management

This enhanced call logging system provides comprehensive tracking and management of all call activities with detailed event logging and recording capabilities.
