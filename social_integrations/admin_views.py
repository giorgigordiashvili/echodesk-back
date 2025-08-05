import requests
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.http import JsonResponse
from django.urls import reverse
from .models import FacebookPageConnection


@staff_member_required
@login_required
def facebook_oauth_admin_start(request):
    """Start Facebook OAuth flow from Django admin"""
    try:
        fb_app_id = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_APP_ID')
        if not fb_app_id:
            messages.error(request, 'Facebook App ID not configured')
            return redirect('admin:social_integrations_facebookpageconnection_changelist')
        
        # Use admin callback URL - build manually since reverse might fail in tenant context
        callback_path = '/api/social/admin/facebook/oauth/callback/'
        redirect_uri = request.build_absolute_uri(callback_path)
        
        # Include user info in state parameter
        state = f'user={request.user.id}&tenant={getattr(request, "tenant", "amanati")}'
        
        # Facebook OAuth URL for business pages with pages_messaging scope
        oauth_url = (
            f"https://www.facebook.com/v23.0/dialog/oauth?"
            f"client_id={fb_app_id}&"
            f"redirect_uri={redirect_uri}&"
            f"scope=pages_manage_metadata,pages_messaging,pages_read_engagement,pages_show_list&"
            f"state={state}&"
            f"response_type=code"
        )
        
        return redirect(oauth_url)
        
    except Exception as e:
        messages.error(request, f'Failed to start Facebook OAuth: {str(e)}')
        return redirect('admin:social_integrations_facebookpageconnection_changelist')


@staff_member_required
def facebook_oauth_admin_callback(request):
    """Handle Facebook OAuth callback and create page connections"""
    try:
        # Get parameters from Facebook callback
        code = request.GET.get('code')
        error = request.GET.get('error')
        error_description = request.GET.get('error_description')
        state = request.GET.get('state')
        
        # Handle Facebook errors
        if error:
            messages.error(request, f'Facebook OAuth failed: {error_description or error}')
            return redirect('admin:social_integrations_facebookpageconnection_changelist')
        
        if not code:
            messages.error(request, 'No authorization code received from Facebook')
            return redirect('admin:social_integrations_facebookpageconnection_changelist')
        
        # Parse state to get user info
        user_id = None
        if state:
            for param in state.split('&'):
                if param.startswith('user='):
                    user_id = param.split('=')[1]
                    break
        
        if not user_id or str(request.user.id) != user_id:
            messages.error(request, 'Invalid state parameter')
            return redirect('admin:social_integrations_facebookpageconnection_changelist')
        
        # Exchange code for access token
        fb_app_id = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_APP_ID')
        fb_app_secret = getattr(settings, 'SOCIAL_INTEGRATIONS', {}).get('FACEBOOK_APP_SECRET')
        callback_path = '/api/social/admin/facebook/oauth/callback/'
        redirect_uri = request.build_absolute_uri(callback_path)
        
        token_url = 'https://graph.facebook.com/v23.0/oauth/access_token'
        token_params = {
            'client_id': fb_app_id,
            'client_secret': fb_app_secret,
            'redirect_uri': redirect_uri,
            'code': code
        }
        
        token_response = requests.get(token_url, params=token_params)
        if token_response.status_code != 200:
            messages.error(request, 'Failed to exchange code for access token')
            return redirect('admin:social_integrations_facebookpageconnection_changelist')
        
        token_data = token_response.json()
        user_access_token = token_data.get('access_token')
        
        if not user_access_token:
            messages.error(request, 'No access token received from Facebook')
            return redirect('admin:social_integrations_facebookpageconnection_changelist')
        
        # Get user's pages
        pages_url = 'https://graph.facebook.com/v23.0/me/accounts'
        pages_params = {
            'access_token': user_access_token,
            'fields': 'id,name,access_token,category,category_list'
        }
        
        pages_response = requests.get(pages_url, params=pages_params)
        if pages_response.status_code != 200:
            messages.error(request, 'Failed to fetch Facebook pages')
            return redirect('admin:social_integrations_facebookpageconnection_changelist')
        
        pages_data = pages_response.json()
        pages = pages_data.get('data', [])
        
        if not pages:
            messages.warning(request, 'No Facebook pages found. Make sure you have admin access to Facebook pages.')
            return redirect('admin:social_integrations_facebookpageconnection_changelist')
        
        # Create or update page connections
        created_count = 0
        updated_count = 0
        
        for page in pages:
            page_id = page.get('id')
            page_name = page.get('name')
            page_access_token = page.get('access_token')
            
            if not all([page_id, page_name, page_access_token]):
                continue
            
            # Create or update the page connection
            connection, created = FacebookPageConnection.objects.update_or_create(
                user=request.user,
                page_id=page_id,
                defaults={
                    'page_name': page_name,
                    'page_access_token': page_access_token,
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        # Show success message
        if created_count > 0:
            messages.success(request, f'Successfully connected {created_count} Facebook page(s)')
        if updated_count > 0:
            messages.success(request, f'Updated {updated_count} existing Facebook page connection(s)')
        
        return redirect('admin:social_integrations_facebookpageconnection_changelist')
        
    except Exception as e:
        messages.error(request, f'Facebook OAuth callback failed: {str(e)}')
        return redirect('admin:social_integrations_facebookpageconnection_changelist')
