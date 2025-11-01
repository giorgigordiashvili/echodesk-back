"""
Email utilities for ecommerce_crm app
"""
import logging
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_email(
    subject,
    recipient_email,
    template_name,
    context=None,
    from_email=None
):
    """
    Send an email using a template

    Args:
        subject: Email subject
        recipient_email: Recipient email address
        template_name: Template name (without path and extension)
        context: Template context dictionary
        from_email: Sender email (defaults to settings.DEFAULT_FROM_EMAIL)

    Returns:
        bool: True if email sent successfully, False otherwise
    """
    if context is None:
        context = {}

    if from_email is None:
        from_email = settings.DEFAULT_FROM_EMAIL

    try:
        # Add common context variables
        context['site_name'] = settings.SENDGRID_FROM_NAME
        context['frontend_url'] = f"https://{settings.FRONTEND_BASE_URL}"

        # Render HTML email
        html_content = render_to_string(
            f'ecommerce_crm/emails/{template_name}.html',
            context
        )

        # Create plain text version
        text_content = strip_tags(html_content)

        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[recipient_email]
        )
        email.attach_alternative(html_content, "text/html")

        # Send email
        email.send(fail_silently=False)

        logger.info(f"Email sent successfully to {recipient_email}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {recipient_email}: {str(e)}")
        return False


def send_welcome_email(client):
    """
    Send welcome email to newly registered client

    Args:
        client: EcommerceClient instance

    Returns:
        bool: True if email sent successfully
    """
    context = {
        'client_name': client.first_name or 'Valued Customer',
        'client_email': client.email,
    }

    return send_email(
        subject=f'Welcome to {settings.SENDGRID_FROM_NAME}!',
        recipient_email=client.email,
        template_name='welcome',
        context=context
    )


def send_password_reset_email(client, reset_token):
    """
    Send password reset email to client

    Args:
        client: EcommerceClient instance
        reset_token: Password reset token

    Returns:
        bool: True if email sent successfully
    """
    # Construct reset URL
    reset_url = f"https://{settings.FRONTEND_BASE_URL}/reset-password?token={reset_token}"

    context = {
        'client_name': client.first_name or 'Valued Customer',
        'reset_url': reset_url,
        'reset_token': reset_token,
    }

    return send_email(
        subject='Reset Your Password',
        recipient_email=client.email,
        template_name='password_reset',
        context=context
    )
