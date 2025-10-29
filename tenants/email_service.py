"""
SendGrid Email Service for EchoDesk
Handles all email sending functionality including tenant creation and user invitations
"""

import logging
from typing import Optional, Dict, Any
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from django.conf import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service class for sending emails via SendGrid"""

    def __init__(self):
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL
        self.from_name = settings.SENDGRID_FROM_NAME

        if not self.api_key:
            logger.warning("SendGrid API key not configured. Emails will not be sent.")

    def _send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None
    ) -> bool:
        """
        Internal method to send an email via SendGrid

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML version of email content
            plain_content: Plain text version (optional)

        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.api_key:
            logger.warning(f"Email not sent to {to_email}: SendGrid API key not configured")
            return False

        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                html_content=Content("text/html", html_content)
            )

            if plain_content:
                message.plain_text_content = Content("text/plain", plain_content)

            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)

            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email to {to_email}. Status: {response.status_code}")
                return False

        except Exception as e:
            error_details = str(e)

            # Extract more details from SendGrid errors
            if hasattr(e, 'body'):
                try:
                    import json
                    error_body = json.loads(e.body) if isinstance(e.body, (str, bytes)) else e.body
                    error_details = f"{error_details} - Details: {error_body}"
                except:
                    pass

            logger.error(f"Error sending email to {to_email}: {error_details}")

            # Log helpful hints for common errors
            if '403' in error_details or 'Forbidden' in error_details:
                logger.error(
                    "SendGrid 403 Error - Possible causes:\n"
                    "1. API Key doesn't have 'Mail Send' permission\n"
                    "2. Sender email not verified in SendGrid\n"
                    "3. API Key is invalid or expired\n"
                    f"Current from_email: {self.from_email}\n"
                    "Fix: Verify sender at https://app.sendgrid.com/settings/sender_auth"
                )

            return False

    def send_tenant_created_email(
        self,
        tenant_email: str,
        tenant_name: str,
        admin_name: str,
        frontend_url: str,
        schema_name: str
    ) -> bool:
        """
        Send welcome email to newly created tenant admin

        Args:
            tenant_email: Admin email address
            tenant_name: Organization/tenant name
            admin_name: Admin's full name
            frontend_url: URL to access the tenant dashboard
            schema_name: Tenant schema identifier

        Returns:
            bool: True if email sent successfully
        """
        subject = f"Welcome to EchoDesk - Your Account is Ready!"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4F46E5; color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background-color: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
                .button {{ display: inline-block; background-color: #4F46E5; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .info-box {{ background-color: white; padding: 20px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #4F46E5; }}
                .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Welcome to EchoDesk!</h1>
                </div>
                <div class="content">
                    <p>Hello {admin_name},</p>

                    <p>Congratulations! Your EchoDesk account has been successfully created for <strong>{tenant_name}</strong>.</p>

                    <div class="info-box">
                        <p><strong>Your Account Details:</strong></p>
                        <ul>
                            <li><strong>Organization:</strong> {tenant_name}</li>
                            <li><strong>Email:</strong> {tenant_email}</li>
                            <li><strong>Tenant ID:</strong> {schema_name}</li>
                        </ul>
                    </div>

                    <p>You can now access your dashboard and start managing your customer support operations:</p>

                    <div style="text-align: center;">
                        <a href="{frontend_url}" class="button">Access Your Dashboard</a>
                    </div>

                    <p><strong>Getting Started:</strong></p>
                    <ul>
                        <li>Invite team members to your organization</li>
                        <li>Set up your ticket forms and custom fields</li>
                        <li>Integrate your communication channels</li>
                        <li>Configure your workflow and automation rules</li>
                    </ul>

                    <p>If you have any questions or need assistance, our support team is here to help!</p>

                    <p>Best regards,<br>The EchoDesk Team</p>
                </div>
                <div class="footer">
                    <p>© 2025 EchoDesk. All rights reserved.</p>
                    <p>This is an automated message, please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """

        plain_content = f"""
        Welcome to EchoDesk!

        Hello {admin_name},

        Congratulations! Your EchoDesk account has been successfully created for {tenant_name}.

        Your Account Details:
        - Organization: {tenant_name}
        - Email: {tenant_email}
        - Tenant ID: {schema_name}

        Access your dashboard: {frontend_url}

        Getting Started:
        - Invite team members to your organization
        - Set up your ticket forms and custom fields
        - Integrate your communication channels
        - Configure your workflow and automation rules

        If you have any questions or need assistance, our support team is here to help!

        Best regards,
        The EchoDesk Team

        © 2025 EchoDesk. All rights reserved.
        """

        return self._send_email(tenant_email, subject, html_content, plain_content)

    def send_user_invitation_email(
        self,
        user_email: str,
        user_name: str,
        tenant_name: str,
        temporary_password: str,
        frontend_url: str,
        invited_by: str
    ) -> bool:
        """
        Send invitation email to new user with temporary password

        Args:
            user_email: New user's email address
            user_name: New user's full name
            tenant_name: Organization name
            temporary_password: One-time password for first login
            frontend_url: URL to access the dashboard
            invited_by: Name of the person who invited this user

        Returns:
            bool: True if email sent successfully
        """
        subject = f"You've been invited to join {tenant_name} on EchoDesk"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #4F46E5; color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background-color: #f9fafb; padding: 30px; border-radius: 0 0 8px 8px; }}
                .button {{ display: inline-block; background-color: #4F46E5; color: white; padding: 12px 30px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .password-box {{ background-color: #FEF3C7; padding: 20px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #F59E0B; }}
                .password {{ font-family: monospace; font-size: 18px; font-weight: bold; color: #D97706; letter-spacing: 2px; }}
                .warning {{ background-color: #FEE2E2; padding: 15px; border-radius: 6px; margin: 20px 0; border-left: 4px solid #EF4444; }}
                .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>You're Invited!</h1>
                </div>
                <div class="content">
                    <p>Hello {user_name},</p>

                    <p>{invited_by} has invited you to join <strong>{tenant_name}</strong> on EchoDesk.</p>

                    <p>EchoDesk is a powerful customer support platform that helps teams manage tickets, communications, and customer relationships efficiently.</p>

                    <div class="password-box">
                        <p><strong>⚠️ Your Temporary Password:</strong></p>
                        <p class="password">{temporary_password}</p>
                        <p style="margin-top: 10px; font-size: 14px;">Please keep this password secure and do not share it with anyone.</p>
                    </div>

                    <div class="warning">
                        <p><strong>Important Security Notice:</strong></p>
                        <p>You will be required to change this password on your first login. This is a one-time password that expires after first use.</p>
                    </div>

                    <p><strong>To get started:</strong></p>
                    <ol>
                        <li>Click the button below to access your dashboard</li>
                        <li>Login with your email and the temporary password above</li>
                        <li>Create a new secure password when prompted</li>
                        <li>Start collaborating with your team!</li>
                    </ol>

                    <div style="text-align: center;">
                        <a href="{frontend_url}" class="button">Accept Invitation & Login</a>
                    </div>

                    <p>If you did not expect this invitation or believe it was sent in error, please ignore this email.</p>

                    <p>Best regards,<br>The EchoDesk Team</p>
                </div>
                <div class="footer">
                    <p>© 2025 EchoDesk. All rights reserved.</p>
                    <p>This is an automated message, please do not reply to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """

        plain_content = f"""
        You're Invited!

        Hello {user_name},

        {invited_by} has invited you to join {tenant_name} on EchoDesk.

        Your Temporary Password: {temporary_password}

        IMPORTANT SECURITY NOTICE:
        You will be required to change this password on your first login. This is a one-time password that expires after first use.

        To get started:
        1. Visit: {frontend_url}
        2. Login with your email and the temporary password above
        3. Create a new secure password when prompted
        4. Start collaborating with your team!

        Please keep this password secure and do not share it with anyone.

        If you did not expect this invitation or believe it was sent in error, please ignore this email.

        Best regards,
        The EchoDesk Team

        © 2025 EchoDesk. All rights reserved.
        """

        return self._send_email(user_email, subject, html_content, plain_content)


# Singleton instance
email_service = EmailService()
