import os
import requests
from datetime import datetime
from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import (
    FacebookPageConnection, FacebookMessage, 
    InstagramAccountConnection, InstagramMessage,
    WhatsAppBusinessConnection, WhatsAppMessage
)
from .serializers import (
    FacebookPageConnectionSerializer, FacebookMessageSerializer, 
    InstagramAccountConnectionSerializer, InstagramMessageSerializer,
    WhatsAppBusinessConnectionSerializer, WhatsAppMessageSerializer
)


def convert_facebook_timestamp(timestamp):
    """Convert Facebook timestamp (Unix timestamp in milliseconds or seconds) to datetime object"""
    try:
        if timestamp == 0:
            return timezone.now()
        
        # Facebook timestamps can be in seconds or milliseconds
        # If timestamp is very large, it's probably in milliseconds
        if timestamp > 10000000000:  # If timestamp is greater than year 2286 in seconds, it's milliseconds
            timestamp = timestamp / 1000
        
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (ValueError, TypeError):
        return timezone.now()


def find_tenant_by_instagram_account_id(instagram_account_id):
    """Find which tenant schema contains the given Instagram account ID"""
    from django.db import connection
    from tenants.models import Tenant
    from tenant_schemas.utils import schema_context
    
    # Get all tenant schemas
    tenants = Tenant.objects.all()
    
    for tenant in tenants:
        try:
            # Switch to tenant schema and check if account exists
            with schema_context(tenant.schema_name):
                from social_integrations.models import InstagramAccountConnection
                if InstagramAccountConnection.objects.filter(instagram_account_id=instagram_account_id, is_active=True).exists():
                    return tenant.schema_name
        except Exception as e:
            # Skip tenant if there's an error (e.g., table doesn't exist)
            continue
    
    return None
