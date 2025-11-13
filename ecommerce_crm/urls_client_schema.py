"""
URL configuration specifically for ecommerce client schema generation.
This module contains ONLY client-facing endpoints to generate a clean client API schema.
"""
from django.urls import path, include
from ecommerce_crm.urls import client_router
from ecommerce_crm.views import (
    register_client,
    login_client,
    refresh_client_token,
    verify_email,
    resend_verification_code,
    get_current_client,
    request_password_reset,
    confirm_password_reset,
)
from ecommerce_crm.views_client import (
    add_client_card,
    list_client_cards,
    delete_client_card,
    set_default_client_card,
)

urlpatterns = [
    # Client authentication endpoints (public access)
    path('api/ecommerce/clients/register/', register_client, name='register-client'),
    path('api/ecommerce/clients/login/', login_client, name='login-client'),
    path('api/ecommerce/clients/refresh-token/', refresh_client_token, name='refresh-client-token'),
    path('api/ecommerce/clients/verify/', verify_email, name='verify-email'),
    path('api/ecommerce/clients/resend-code/', resend_verification_code, name='resend-verification-code'),
    path('api/ecommerce/clients/me/', get_current_client, name='current-client'),
    path('api/ecommerce/clients/password-reset/request/', request_password_reset, name='password-reset-request'),
    path('api/ecommerce/clients/password-reset/confirm/', confirm_password_reset, name='password-reset-confirm'),

    # Client-facing card management endpoints (requires client JWT)
    path('api/ecommerce/client/cards/add/', add_client_card, name='client-add-card'),
    path('api/ecommerce/client/cards/', list_client_cards, name='client-list-cards'),
    path('api/ecommerce/client/cards/<int:card_id>/delete/', delete_client_card, name='client-delete-card'),
    path('api/ecommerce/client/cards/<int:card_id>/set-default/', set_default_client_card, name='client-set-default-card'),

    # Client-facing endpoints (requires client JWT)
    path('api/ecommerce/client/', include(client_router.urls)),
]
