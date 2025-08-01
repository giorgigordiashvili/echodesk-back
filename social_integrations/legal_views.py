from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging

logger = logging.getLogger(__name__)


def privacy_policy(request):
    """Privacy Policy page for Facebook App compliance"""
    return render(request, 'legal/privacy_policy.html')


def terms_of_service(request):
    """Terms of Service page for Facebook App compliance"""
    return render(request, 'legal/terms_of_service.html')


@csrf_exempt
@require_http_methods(["GET", "POST"])
def user_data_deletion(request):
    """Handle Facebook user data deletion requests"""
    if request.method == 'GET':
        # Show information page about data deletion
        return render(request, 'legal/data_deletion.html')
    
    elif request.method == 'POST':
        # Handle Facebook data deletion callback
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST.dict()
            
            signed_request = data.get('signed_request')
            if not signed_request:
                return JsonResponse({
                    'error': 'Missing signed_request parameter'
                }, status=400)
            
            # Parse the signed request (you would normally verify the signature)
            # For now, we'll just log the deletion request
            
            # In a real implementation, you would:
            # 1. Verify the signed_request signature using your app secret
            # 2. Extract the user_id from the signed_request
            # 3. Delete all user data from your database
            # 4. Return a confirmation URL
            
            confirmation_code = f"DEL_{signed_request[:10]}"
            deletion_url = request.build_absolute_uri(f'/legal/data-deletion-status/?code={confirmation_code}')
            
            return JsonResponse({
                'url': deletion_url,
                'confirmation_code': confirmation_code
            })
            
        except Exception as e:
            return JsonResponse({
                'error': f'Failed to process deletion request: {str(e)}'
            }, status=500)


def data_deletion_status(request):
    """Show data deletion status"""
    confirmation_code = request.GET.get('code')
    return render(request, 'legal/data_deletion_status.html', {
        'confirmation_code': confirmation_code
    })


@csrf_exempt
@require_http_methods(["POST"])
def deauthorize_callback(request):
    """Handle Facebook/Instagram app deauthorization callback
    
    This endpoint handles when users remove your app from their Facebook/Instagram account.
    Since Instagram uses Facebook's infrastructure, this single endpoint handles both platforms.
    """
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST.dict()
        
        signed_request = data.get('signed_request')
        if not signed_request:
            logger.warning("Deauthorize callback received without signed_request")
            return JsonResponse({
                'error': 'Missing signed_request parameter'
            }, status=400)
        
        # In a real implementation, you would:
        # 1. Verify the signed_request signature using your app secret
        # 2. Extract the user_id from the signed_request
        # 3. Revoke access tokens and remove connection data
        # 4. Log the deauthorization event
        
        # For now, we'll just log the deauthorization request
        logger.info(f"App deauthorization request received: {signed_request[:20]}...")
        
        # Parse signed request to get user ID (simplified - you should verify signature)
        try:
            import base64
            # This is a simplified parsing - in production, verify the signature first
            payload = signed_request.split('.')[1]
            # Add padding if needed
            payload += '=' * (4 - len(payload) % 4)
            decoded = base64.b64decode(payload)
            parsed_data = json.loads(decoded)
            user_id = parsed_data.get('user_id')
            
            if user_id:
                # Here you would remove the user's connections from your database
                # For both Facebook and Instagram connections
                logger.info(f"Processing deauthorization for user: {user_id}")
                
                # TODO: Implement actual deauthorization logic:
                # - Remove FacebookPageConnection records for this user
                # - Remove InstagramAccountConnection records for this user  
                # - Revoke any stored access tokens
                # - Clean up related data
        
        except Exception as parse_error:
            logger.error(f"Failed to parse signed_request: {parse_error}")
        
        return JsonResponse({
            'status': 'success',
            'message': 'Deauthorization processed'
        })
        
    except Exception as e:
        logger.error(f"Failed to process deauthorization: {e}")
        return JsonResponse({
            'error': f'Failed to process deauthorization: {str(e)}'
        }, status=500)
