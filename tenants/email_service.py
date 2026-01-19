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


# Multi-language email translations
EMAIL_TRANSLATIONS = {
    'invitation': {
        'en': {
            'greeting': "You're Invited!",
            'hello': 'Hello {user_name},',
            'invited_by': '{inviter} has invited you to join <strong>{tenant_name}</strong> on EchoDesk.',
            'description': 'EchoDesk is a powerful customer support platform that helps teams manage tickets, communications, and customer relationships efficiently.',
            'password_label': 'Your Temporary Password:',
            'password_warning': 'Please keep this password secure and do not share it with anyone.',
            'security_title': 'Important Security Notice:',
            'security_warning': 'You will be required to change this password on your first login. This is a one-time password that expires after first use.',
            'steps_title': 'To get started:',
            'step1': 'Click the button below to access your dashboard',
            'step2': 'Login with your email and the temporary password above',
            'step3': 'Create a new secure password when prompted',
            'step4': 'Start collaborating with your team!',
            'button': 'Accept Invitation & Login',
            'ignore_notice': 'If you did not expect this invitation or believe it was sent in error, please ignore this email.',
            'regards': 'Best regards,<br>The EchoDesk Team',
            'copyright': '© 2025 EchoDesk. All rights reserved.',
            'automated': 'This is an automated message, please do not reply to this email.',
        },
        'ka': {
            'greeting': 'თქვენ მოწვეული ხართ!',
            'hello': 'გამარჯობა {user_name},',
            'invited_by': '{inviter}-მა მოგიწვიათ <strong>{tenant_name}</strong>-ში EchoDesk-ზე.',
            'description': 'EchoDesk არის მძლავრი მომხმარებელთა მხარდაჭერის პლატფორმა, რომელიც გუნდებს ეხმარება ბილეთების, კომუნიკაციების და კლიენტებთან ურთიერთობების ეფექტურად მართვაში.',
            'password_label': 'თქვენი დროებითი პაროლი:',
            'password_warning': 'გთხოვთ, შეინახოთ ეს პაროლი უსაფრთხოდ და არავის გაუზიაროთ.',
            'security_title': 'მნიშვნელოვანი უსაფრთხოების შეტყობინება:',
            'security_warning': 'პირველი შესვლისას მოგიწევთ ამ პაროლის შეცვლა. ეს არის ერთჯერადი პაროლი, რომელიც იწურება პირველი გამოყენების შემდეგ.',
            'steps_title': 'დასაწყებად:',
            'step1': 'დააჭირეთ ქვემოთ მოცემულ ღილაკს დაფაზე შესასვლელად',
            'step2': 'შედით თქვენი ელფოსტით და ზემოთ მოცემული დროებითი პაროლით',
            'step3': 'შექმენით ახალი უსაფრთხო პაროლი მოთხოვნისას',
            'step4': 'დაიწყეთ თანამშრომლობა თქვენს გუნდთან!',
            'button': 'მოწვევის მიღება და შესვლა',
            'ignore_notice': 'თუ ეს მოწვევა არ ელოდით ან მიგაჩნიათ, რომ შეცდომით გამოგეგზავნათ, გთხოვთ, უგულებელყოთ ეს ელფოსტა.',
            'regards': 'პატივისცემით,<br>EchoDesk-ის გუნდი',
            'copyright': '© 2025 EchoDesk. ყველა უფლება დაცულია.',
            'automated': 'ეს არის ავტომატური შეტყობინება, გთხოვთ, არ უპასუხოთ ამ ელფოსტას.',
        },
        'ru': {
            'greeting': 'Вы приглашены!',
            'hello': 'Здравствуйте {user_name},',
            'invited_by': '{inviter} пригласил вас присоединиться к <strong>{tenant_name}</strong> на EchoDesk.',
            'description': 'EchoDesk — это мощная платформа поддержки клиентов, которая помогает командам эффективно управлять заявками, коммуникациями и отношениями с клиентами.',
            'password_label': 'Ваш временный пароль:',
            'password_warning': 'Пожалуйста, храните этот пароль в безопасности и никому его не сообщайте.',
            'security_title': 'Важное уведомление о безопасности:',
            'security_warning': 'При первом входе вам потребуется сменить этот пароль. Это одноразовый пароль, который становится недействительным после первого использования.',
            'steps_title': 'Чтобы начать:',
            'step1': 'Нажмите кнопку ниже для доступа к панели управления',
            'step2': 'Войдите, используя вашу электронную почту и временный пароль выше',
            'step3': 'Создайте новый безопасный пароль при появлении запроса',
            'step4': 'Начните сотрудничество с вашей командой!',
            'button': 'Принять приглашение и войти',
            'ignore_notice': 'Если вы не ожидали этого приглашения или считаете, что оно было отправлено по ошибке, просто проигнорируйте это письмо.',
            'regards': 'С уважением,<br>Команда EchoDesk',
            'copyright': '© 2025 EchoDesk. Все права защищены.',
            'automated': 'Это автоматическое сообщение, пожалуйста, не отвечайте на это письмо.',
        },
    },
    'new_password': {
        'en': {
            'greeting': 'Password Reset',
            'hello': 'Hello {user_name},',
            'message': 'A new password has been generated for your account at <strong>{tenant_name}</strong>.',
            'password_label': 'Your New Temporary Password:',
            'password_warning': 'Please keep this password secure and do not share it with anyone.',
            'security_title': 'Important Security Notice:',
            'security_warning': 'You will be required to change this password on your next login.',
            'button': 'Login Now',
            'ignore_notice': 'If you did not request a new password, please contact your administrator immediately.',
            'regards': 'Best regards,<br>The EchoDesk Team',
            'copyright': '© 2025 EchoDesk. All rights reserved.',
            'automated': 'This is an automated message, please do not reply to this email.',
        },
        'ka': {
            'greeting': 'პაროლის აღდგენა',
            'hello': 'გამარჯობა {user_name},',
            'message': 'თქვენი ანგარიშისთვის <strong>{tenant_name}</strong>-ში შეიქმნა ახალი პაროლი.',
            'password_label': 'თქვენი ახალი დროებითი პაროლი:',
            'password_warning': 'გთხოვთ, შეინახოთ ეს პაროლი უსაფრთხოდ და არავის გაუზიაროთ.',
            'security_title': 'მნიშვნელოვანი უსაფრთხოების შეტყობინება:',
            'security_warning': 'შემდეგი შესვლისას მოგიწევთ ამ პაროლის შეცვლა.',
            'button': 'შესვლა',
            'ignore_notice': 'თუ თქვენ არ მოითხოვეთ ახალი პაროლი, გთხოვთ, დაუყოვნებლივ დაუკავშირდეთ თქვენს ადმინისტრატორს.',
            'regards': 'პატივისცემით,<br>EchoDesk-ის გუნდი',
            'copyright': '© 2025 EchoDesk. ყველა უფლება დაცულია.',
            'automated': 'ეს არის ავტომატური შეტყობინება, გთხოვთ, არ უპასუხოთ ამ ელფოსტას.',
        },
        'ru': {
            'greeting': 'Сброс пароля',
            'hello': 'Здравствуйте {user_name},',
            'message': 'Для вашей учетной записи в <strong>{tenant_name}</strong> был сгенерирован новый пароль.',
            'password_label': 'Ваш новый временный пароль:',
            'password_warning': 'Пожалуйста, храните этот пароль в безопасности и никому его не сообщайте.',
            'security_title': 'Важное уведомление о безопасности:',
            'security_warning': 'При следующем входе вам потребуется сменить этот пароль.',
            'button': 'Войти',
            'ignore_notice': 'Если вы не запрашивали новый пароль, пожалуйста, немедленно свяжитесь с вашим администратором.',
            'regards': 'С уважением,<br>Команда EchoDesk',
            'copyright': '© 2025 EchoDesk. Все права защищены.',
            'automated': 'Это автоматическое сообщение, пожалуйста, не отвечайте на это письмо.',
        },
    },
}


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
        invited_by: str,
        language: str = 'en'
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
            language: Language code (en, ka, ru)

        Returns:
            bool: True if email sent successfully
        """
        # Get translations for the specified language, fallback to English
        t = EMAIL_TRANSLATIONS['invitation'].get(language, EMAIL_TRANSLATIONS['invitation']['en'])

        subject = f"{tenant_name} - Echodesk"

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
                    <h1>{t['greeting']}</h1>
                </div>
                <div class="content">
                    <p>{t['hello'].format(user_name=user_name)}</p>

                    <p>{t['invited_by'].format(inviter=invited_by, tenant_name=tenant_name)}</p>

                    <p>{t['description']}</p>

                    <div class="password-box">
                        <p><strong>⚠️ {t['password_label']}</strong></p>
                        <p class="password">{temporary_password}</p>
                        <p style="margin-top: 10px; font-size: 14px;">{t['password_warning']}</p>
                    </div>

                    <div class="warning">
                        <p><strong>{t['security_title']}</strong></p>
                        <p>{t['security_warning']}</p>
                    </div>

                    <p><strong>{t['steps_title']}</strong></p>
                    <ol>
                        <li>{t['step1']}</li>
                        <li>{t['step2']}</li>
                        <li>{t['step3']}</li>
                        <li>{t['step4']}</li>
                    </ol>

                    <div style="text-align: center;">
                        <a href="{frontend_url}" class="button">{t['button']}</a>
                    </div>

                    <p>{t['ignore_notice']}</p>

                    <p>{t['regards']}</p>
                </div>
                <div class="footer">
                    <p>{t['copyright']}</p>
                    <p>{t['automated']}</p>
                </div>
            </div>
        </body>
        </html>
        """

        plain_content = f"""
        {t['greeting']}

        {t['hello'].format(user_name=user_name)}

        {t['invited_by'].format(inviter=invited_by, tenant_name=tenant_name).replace('<strong>', '').replace('</strong>', '')}

        {t['password_label']} {temporary_password}

        {t['security_title']}
        {t['security_warning']}

        {t['steps_title']}
        1. {t['step1']}
        2. {t['step2']}
        3. {t['step3']}
        4. {t['step4']}

        {t['password_warning']}

        {t['ignore_notice']}

        {t['regards'].replace('<br>', '')}

        {t['copyright']}
        """

        return self._send_email(user_email, subject, html_content, plain_content)

    def send_new_password_email(
        self,
        user_email: str,
        user_name: str,
        tenant_name: str,
        new_password: str,
        frontend_url: str,
        language: str = 'en'
    ) -> bool:
        """
        Send new password email to user

        Args:
            user_email: User's email address
            user_name: User's full name
            tenant_name: Organization name
            new_password: New temporary password
            frontend_url: URL to access the dashboard
            language: Language code (en, ka, ru)

        Returns:
            bool: True if email sent successfully
        """
        # Get translations for the specified language, fallback to English
        t = EMAIL_TRANSLATIONS['new_password'].get(language, EMAIL_TRANSLATIONS['new_password']['en'])

        subject = f"{tenant_name} - Echodesk"

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
                    <h1>{t['greeting']}</h1>
                </div>
                <div class="content">
                    <p>{t['hello'].format(user_name=user_name)}</p>

                    <p>{t['message'].format(tenant_name=tenant_name)}</p>

                    <div class="password-box">
                        <p><strong>⚠️ {t['password_label']}</strong></p>
                        <p class="password">{new_password}</p>
                        <p style="margin-top: 10px; font-size: 14px;">{t['password_warning']}</p>
                    </div>

                    <div class="warning">
                        <p><strong>{t['security_title']}</strong></p>
                        <p>{t['security_warning']}</p>
                    </div>

                    <div style="text-align: center;">
                        <a href="{frontend_url}" class="button">{t['button']}</a>
                    </div>

                    <p>{t['ignore_notice']}</p>

                    <p>{t['regards']}</p>
                </div>
                <div class="footer">
                    <p>{t['copyright']}</p>
                    <p>{t['automated']}</p>
                </div>
            </div>
        </body>
        </html>
        """

        plain_content = f"""
        {t['greeting']}

        {t['hello'].format(user_name=user_name)}

        {t['message'].format(tenant_name=tenant_name).replace('<strong>', '').replace('</strong>', '')}

        {t['password_label']} {new_password}

        {t['security_title']}
        {t['security_warning']}

        {t['password_warning']}

        {t['ignore_notice']}

        {t['regards'].replace('<br>', '')}

        {t['copyright']}
        """

        return self._send_email(user_email, subject, html_content, plain_content)


# Singleton instance
email_service = EmailService()
