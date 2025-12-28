"""
Email utility functions for IMAP/SMTP operations.
"""
import imaplib
import smtplib
import email
import hashlib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import make_msgid, formataddr, parseaddr, getaddresses, parsedate_to_datetime
from datetime import datetime, timedelta
from typing import Tuple, Optional, List, Dict, Any

from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def test_imap_connection(server: str, port: int, username: str, password: str, use_ssl: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Test IMAP connection credentials.

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        if use_ssl:
            imap = imaplib.IMAP4_SSL(server, port, timeout=10)
        else:
            imap = imaplib.IMAP4(server, port)
            imap.starttls()

        imap.login(username, password)
        imap.logout()
        return True, None
    except imaplib.IMAP4.error as e:
        return False, f"IMAP authentication error: {str(e)}"
    except Exception as e:
        return False, f"IMAP connection error: {str(e)}"


def test_smtp_connection(server: str, port: int, username: str, password: str,
                         use_tls: bool = True, use_ssl: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Test SMTP connection credentials.

    Returns:
        Tuple of (success: bool, error_message: Optional[str])
    """
    try:
        if use_ssl:
            smtp = smtplib.SMTP_SSL(server, port, timeout=10)
        else:
            smtp = smtplib.SMTP(server, port, timeout=10)
            if use_tls:
                smtp.starttls()

        smtp.login(username, password)
        smtp.quit()
        return True, None
    except smtplib.SMTPAuthenticationError as e:
        return False, f"SMTP authentication error: {str(e)}"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"SMTP connection error: {str(e)}"


def get_imap_folders(connection) -> List[str]:
    """
    Get list of available folders from IMAP server.

    Args:
        connection: EmailConnection model instance

    Returns:
        List of folder names
    """
    try:
        if connection.imap_use_ssl:
            imap = imaplib.IMAP4_SSL(connection.imap_server, connection.imap_port, timeout=10)
        else:
            imap = imaplib.IMAP4(connection.imap_server, connection.imap_port)
            imap.starttls()

        imap.login(connection.username, connection.get_password())
        result, folder_list = imap.list()
        imap.logout()

        folders = []
        if result == 'OK':
            for folder_data in folder_list:
                if isinstance(folder_data, bytes):
                    # Parse folder name from IMAP response like: (\HasNoChildren) "/" "INBOX"
                    decoded = folder_data.decode('utf-8', errors='replace')
                    # Extract the folder name (last quoted string or last word)
                    parts = decoded.rsplit('" ', 1)
                    if len(parts) == 2:
                        folder_name = parts[1].strip('"')
                    else:
                        # Fallback: get last part after delimiter
                        parts = decoded.split(' ')
                        folder_name = parts[-1].strip('"')
                    folders.append(folder_name)

        return folders
    except Exception as e:
        logger.error(f"Failed to get IMAP folders: {e}")
        return []


def parse_address_list(address_string: str) -> List[Dict[str, str]]:
    """
    Parse email address list into [{email, name}] format.

    Args:
        address_string: Email address string (e.g., "John Doe <john@example.com>, jane@example.com")

    Returns:
        List of dicts with 'email' and 'name' keys
    """
    addresses = getaddresses([address_string])
    return [{'email': addr[1], 'name': addr[0]} for addr in addresses if addr[1]]


def extract_body(email_message) -> Tuple[str, str]:
    """
    Extract plain text and HTML body from email message.

    Args:
        email_message: email.message.Message object

    Returns:
        Tuple of (body_text, body_html)
    """
    body_text = ''
    body_html = ''

    if email_message.is_multipart():
        for part in email_message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get('Content-Disposition', ''))

            # Skip attachments
            if 'attachment' in content_disposition:
                continue

            try:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    decoded = payload.decode(charset, errors='replace')

                    if content_type == 'text/plain' and not body_text:
                        body_text = decoded
                    elif content_type == 'text/html' and not body_html:
                        body_html = decoded
            except Exception as e:
                logger.warning(f"Failed to decode email part: {e}")
                continue
    else:
        content_type = email_message.get_content_type()
        try:
            payload = email_message.get_payload(decode=True)
            if payload:
                charset = email_message.get_content_charset() or 'utf-8'
                decoded = payload.decode(charset, errors='replace')

                if content_type == 'text/html':
                    body_html = decoded
                else:
                    body_text = decoded
        except Exception as e:
            logger.warning(f"Failed to decode email body: {e}")

    return body_text, body_html


def extract_attachments(email_message, connection) -> List[Dict[str, Any]]:
    """
    Extract and save attachments from email message.

    Args:
        email_message: email.message.Message object
        connection: EmailConnection model instance

    Returns:
        List of attachment dicts with filename, content_type, url, size
    """
    attachments = []

    if not email_message.is_multipart():
        return attachments

    for part in email_message.walk():
        content_disposition = str(part.get('Content-Disposition', ''))
        if 'attachment' not in content_disposition and 'inline' not in content_disposition:
            continue

        # Skip text parts that are part of the body
        if part.get_content_maintype() == 'text' and 'attachment' not in content_disposition:
            continue

        filename = part.get_filename()
        if not filename:
            # Generate filename for inline content
            ext = part.get_content_type().split('/')[-1]
            filename = f"attachment.{ext}"

        content_type = part.get_content_type()

        try:
            payload = part.get_payload(decode=True)
            if payload:
                # Save to storage
                file_path = f'email_attachments/{connection.id}/{timezone.now().strftime("%Y/%m/%d")}/{filename}'
                saved_path = default_storage.save(file_path, ContentFile(payload))
                url = default_storage.url(saved_path)

                attachments.append({
                    'filename': filename,
                    'content_type': content_type,
                    'url': url,
                    'size': len(payload)
                })
        except Exception as e:
            logger.error(f"Failed to save attachment {filename}: {e}")
            continue

    return attachments


def wrap_html_email(body_html: str, signature_html: str = None) -> str:
    """
    Wrap HTML content in a proper email template with inline styles.

    This ensures consistent rendering across email clients like Outlook, Gmail, etc.

    Args:
        body_html: The main email body HTML
        signature_html: Optional signature HTML to append

    Returns:
        Complete HTML email with inline styles
    """
    import re

    def process_images(html):
        """Add explicit width/height styles to images based on their attributes."""
        if not html:
            return html

        def fix_img(match):
            tag = match.group(0)
            attrs = match.group(1)

            # Extract width and height attributes
            width_match = re.search(r'width=["\']?(\d+)["\']?', attrs, re.IGNORECASE)
            height_match = re.search(r'height=["\']?(\d+)["\']?', attrs, re.IGNORECASE)

            if not width_match and not height_match:
                return tag

            width = width_match.group(1) if width_match else None
            height = height_match.group(1) if height_match else None

            # Build style string
            styles = []
            if width:
                styles.append(f'width: {width}px')
            if height:
                styles.append(f'height: {height}px')
            styles.append('max-width: none')  # Override any max-width: 100%

            style_str = '; '.join(styles)

            # Remove existing max-width from style if present
            tag = re.sub(r'max-width:\s*[^;]+;?\s*', '', tag, flags=re.IGNORECASE)

            # Add or update style attribute
            if 'style=' in tag.lower():
                # Append to existing style
                tag = re.sub(
                    r'style=(["\'])([^"\']*)\1',
                    lambda m: f'style="{m.group(2)}; {style_str}"',
                    tag,
                    count=1,
                    flags=re.IGNORECASE
                )
            else:
                # Add new style attribute
                tag = tag.replace('<img ', f'<img style="{style_str}" ', 1)

            return tag

        return re.sub(r'<img\s+([^>]*)>', fix_img, html, flags=re.IGNORECASE)

    # Add default link styling to signature HTML if links don't have inline styles
    styled_signature = signature_html
    if styled_signature:
        # Process images first
        styled_signature = process_images(styled_signature)

        # Find <a> tags without style attribute and add blue color
        def add_link_style(match):
            tag = match.group(0)
            if 'style=' in tag.lower():
                # Already has style, ensure color is set
                if 'color:' not in tag.lower() and 'color :' not in tag.lower():
                    # Add color to existing style
                    tag = re.sub(r'style="', 'style="color: #0066cc; ', tag, flags=re.IGNORECASE)
                    tag = re.sub(r"style='", "style='color: #0066cc; ", tag, flags=re.IGNORECASE)
                return tag
            else:
                # No style attribute, add one
                return tag.replace('<a ', '<a style="color: #0066cc; text-decoration: underline;" ', 1)
        styled_signature = re.sub(r'<a\s[^>]*>', add_link_style, styled_signature, flags=re.IGNORECASE)

    # Build the signature section with proper separator
    signature_section = ""
    if styled_signature:
        signature_section = f'''
        <tr>
            <td style="padding-top: 20px; border-top: 1px solid #e5e5e5; margin-top: 20px;">
                <div style="color: #666666; font-size: 14px; line-height: 1.5;">
                    {styled_signature}
                </div>
            </td>
        </tr>
        '''

    # Wrap in email-safe HTML template
    html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Email</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{font-family: Arial, Helvetica, sans-serif !important;}}
    </style>
    <![endif]-->
    <style type="text/css">
        a {{color: #0066cc; text-decoration: underline;}}
    </style>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333333; background-color: #ffffff;">
    <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="max-width: 600px;">
        <tr>
            <td style="padding: 0;">
                <div style="font-size: 14px; line-height: 1.6; color: #333333;">
                    {body_html}
                </div>
            </td>
        </tr>
        {signature_section}
    </table>
</body>
</html>'''

    return html_template


def compute_thread_id(message_id: str, in_reply_to: str, references: str) -> str:
    """
    Compute a thread ID for grouping related emails.

    Uses the first reference or in_reply_to as thread root.
    For new threads, uses the message ID.

    Args:
        message_id: The Message-ID header
        in_reply_to: The In-Reply-To header
        references: The References header

    Returns:
        A consistent thread ID string
    """
    # Use the first reference (root of thread) as thread ID
    if references:
        first_ref = references.split()[0].strip('<>').strip()
        return hashlib.md5(first_ref.encode()).hexdigest()[:32]
    elif in_reply_to:
        return hashlib.md5(in_reply_to.strip('<>').strip().encode()).hexdigest()[:32]
    else:
        # New thread - use message ID
        return hashlib.md5(message_id.strip('<>').strip().encode()).hexdigest()[:32]


def send_email_smtp(connection, to_emails: List[str], cc_emails: List[str] = None,
                    bcc_emails: List[str] = None, subject: str = '',
                    body_text: str = '', body_html: str = '',
                    reply_to_message_id: str = None, attachments: List[Dict] = None) -> Tuple[str, Any]:
    """
    Send an email via SMTP.

    Args:
        connection: EmailConnection model instance
        to_emails: List of recipient email addresses
        cc_emails: List of CC email addresses
        bcc_emails: List of BCC email addresses
        subject: Email subject
        body_text: Plain text body
        body_html: HTML body
        reply_to_message_id: Message-ID of the email being replied to (for threading)
        attachments: List of attachment dicts (not implemented yet)

    Returns:
        Tuple of (message_id, saved_EmailMessage)
    """
    from .models import EmailMessage, EmailSignature

    cc_emails = cc_emails or []
    bcc_emails = bcc_emails or []
    attachments = attachments or []

    # Check if we should append email signature
    is_reply = reply_to_message_id is not None
    signature_html_content = None
    signature_text_content = None

    try:
        signature = EmailSignature.objects.first()
        if signature and signature.is_enabled:
            # Check if signature should be included (always for new emails, conditional for replies)
            should_include = not is_reply or signature.include_on_reply
            if should_include:
                # Get signature content
                if signature.signature_html:
                    signature_html_content = signature.signature_html
                elif signature.signature_text:
                    # Convert plain text signature to HTML
                    signature_html_content = signature.signature_text.replace('\n', '<br>')

                # Get plain text signature
                if signature.signature_text:
                    signature_text_content = signature.signature_text
                elif signature.signature_html:
                    # Simple HTML to text fallback - strip tags
                    import re
                    sig_text = re.sub(r'<[^>]+>', '', signature.signature_html)
                    sig_text = sig_text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').strip()
                    signature_text_content = sig_text
    except Exception as e:
        logger.warning(f"Failed to get email signature: {e}")

    # Append signature to plain text body
    final_body_text = body_text
    if signature_text_content and body_text:
        final_body_text = f"{body_text}\n\n--\n{signature_text_content}"

    # Wrap HTML body in proper email template with signature
    final_body_html = None
    if body_html:
        final_body_html = wrap_html_email(body_html, signature_html_content)

    # Create message
    if final_body_html and final_body_text:
        msg = MIMEMultipart('alternative')
        msg.attach(MIMEText(final_body_text, 'plain', 'utf-8'))
        msg.attach(MIMEText(final_body_html, 'html', 'utf-8'))
    elif final_body_html:
        msg = MIMEText(final_body_html, 'html', 'utf-8')
    else:
        msg = MIMEText(final_body_text or '', 'plain', 'utf-8')

    # Set headers
    msg['Message-ID'] = make_msgid()
    msg['From'] = formataddr((connection.display_name or '', connection.email_address))
    msg['To'] = ', '.join(to_emails)
    if cc_emails:
        msg['Cc'] = ', '.join(cc_emails)
    msg['Subject'] = subject
    msg['Date'] = timezone.now().strftime('%a, %d %b %Y %H:%M:%S %z')

    # Handle reply threading
    thread_id = None
    original = None
    if reply_to_message_id:
        original = EmailMessage.objects.filter(message_id=reply_to_message_id).first()
        if original:
            msg['In-Reply-To'] = original.message_id
            refs = f"{original.references} {original.message_id}".strip()
            msg['References'] = refs
            thread_id = original.thread_id

    if not thread_id:
        thread_id = compute_thread_id(msg['Message-ID'], '', '')

    # Send via SMTP
    try:
        if connection.smtp_use_ssl:
            smtp = smtplib.SMTP_SSL(connection.smtp_server, connection.smtp_port, timeout=30)
        else:
            smtp = smtplib.SMTP(connection.smtp_server, connection.smtp_port, timeout=30)
            if connection.smtp_use_tls:
                smtp.starttls()

        smtp.login(connection.username, connection.get_password())

        all_recipients = to_emails + cc_emails + bcc_emails
        smtp.sendmail(connection.email_address, all_recipients, msg.as_string())
        smtp.quit()

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise

    # Save sent message to database
    sent_message = EmailMessage.objects.create(
        connection=connection,
        message_id=msg['Message-ID'],
        thread_id=thread_id,
        in_reply_to=msg.get('In-Reply-To', ''),
        references=msg.get('References', ''),
        from_email=connection.email_address,
        from_name=connection.display_name or '',
        to_emails=[{'email': e, 'name': ''} for e in to_emails],
        cc_emails=[{'email': e, 'name': ''} for e in cc_emails],
        bcc_emails=[{'email': e, 'name': ''} for e in bcc_emails],
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        timestamp=timezone.now(),
        folder='Sent',
        is_from_business=True,
        is_read=True,
        attachments=[]
    )

    return msg['Message-ID'], sent_message


def _find_sent_folder(imap) -> Optional[str]:
    """
    Find the Sent folder name for this IMAP server.
    Different providers use different names.
    """
    # Common sent folder names across providers
    sent_folder_names = [
        'Sent',
        'INBOX.Sent',
        'Sent Items',
        'Sent Messages',
        '[Gmail]/Sent Mail',
        'INBOX/Sent',
    ]

    try:
        result, folders = imap.list()
        if result != 'OK':
            return None

        available_folders = []
        for folder_data in folders:
            if isinstance(folder_data, bytes):
                # Parse folder name from response like: (\HasNoChildren) "/" "Sent"
                decoded = folder_data.decode('utf-8', errors='replace')
                # Extract folder name (last quoted string or last part)
                if '"' in decoded:
                    parts = decoded.split('"')
                    if len(parts) >= 2:
                        folder_name = parts[-2]
                        available_folders.append(folder_name)

        # Try to find a matching sent folder
        for sent_name in sent_folder_names:
            if sent_name in available_folders:
                return sent_name
            # Case-insensitive match
            for folder in available_folders:
                if folder.lower() == sent_name.lower():
                    return folder

        # Try partial match for 'sent' keyword
        for folder in available_folders:
            if 'sent' in folder.lower():
                return folder

    except Exception as e:
        logger.warning(f"Error finding sent folder: {e}")

    return None


def _sync_folder(imap, connection, folder_name: str, max_messages: int) -> int:
    """
    Sync messages from a specific IMAP folder.

    Returns:
        Number of new messages synced from this folder
    """
    from .models import EmailMessage

    try:
        result, data = imap.select(folder_name, readonly=True)
        if result != 'OK':
            logger.warning(f"Failed to select folder {folder_name}")
            return 0
    except Exception as e:
        logger.warning(f"Error selecting folder {folder_name}: {e}")
        return 0

    # Search for messages from last N days
    since_date = (timezone.now() - timedelta(days=connection.sync_days_back)).strftime('%d-%b-%Y')
    result, data = imap.search(None, f'(SINCE {since_date})')

    if result != 'OK':
        logger.warning(f"Failed to search emails in {folder_name}")
        return 0

    message_ids = data[0].split()

    # Limit to most recent messages
    if len(message_ids) > max_messages:
        message_ids = message_ids[-max_messages:]

    new_count = 0

    for msg_num in message_ids:
        try:
            # Fetch message
            result, msg_data = imap.fetch(msg_num, '(RFC822 FLAGS UID)')
            if result != 'OK':
                continue

            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)

            # Parse Message-ID
            message_id_header = email_message.get('Message-ID', '')
            if not message_id_header:
                message_id_header = make_msgid()

            # Check if already exists
            existing_message = EmailMessage.objects.filter(message_id=message_id_header).first()
            if existing_message:
                # Update folder if it changed (email was moved on server)
                if existing_message.folder != folder_name:
                    existing_message.folder = folder_name
                    existing_message.save(update_fields=['folder'])
                continue

            # Parse sender
            from_header = email_message.get('From', '')
            from_name, from_email_addr = parseaddr(from_header)

            # Parse recipients
            to_emails = parse_address_list(email_message.get('To', ''))
            cc_emails = parse_address_list(email_message.get('Cc', ''))

            # Parse date
            date_str = email_message.get('Date')
            try:
                timestamp = parsedate_to_datetime(date_str)
                if timestamp.tzinfo is None:
                    timestamp = timezone.make_aware(timestamp)
            except Exception:
                timestamp = timezone.now()

            # Get body
            body_text, body_html = extract_body(email_message)

            # Get attachments
            message_attachments = extract_attachments(email_message, connection)

            # Thread ID
            references = email_message.get('References', '')
            in_reply_to = email_message.get('In-Reply-To', '')
            thread_id = compute_thread_id(message_id_header, in_reply_to, references)

            # Determine if from business
            is_from_business = from_email_addr.lower() == connection.email_address.lower()

            # Parse IMAP flags
            flags_data = msg_data[0][0] if len(msg_data[0]) > 0 else b''
            flags = imaplib.ParseFlags(flags_data) if flags_data else ()

            # Get UID
            uid = ''
            uid_match = msg_data[0][0].decode() if isinstance(msg_data[0][0], bytes) else str(msg_data[0][0])
            if 'UID' in uid_match:
                import re
                uid_search = re.search(r'UID (\d+)', uid_match)
                if uid_search:
                    uid = uid_search.group(1)

            # Create message
            EmailMessage.objects.create(
                connection=connection,
                message_id=message_id_header,
                thread_id=thread_id,
                in_reply_to=in_reply_to,
                references=references,
                from_email=from_email_addr,
                from_name=from_name,
                to_emails=to_emails,
                cc_emails=cc_emails,
                subject=email_message.get('Subject', ''),
                body_text=body_text,
                body_html=body_html,
                attachments=message_attachments,
                timestamp=timestamp,
                folder=folder_name,
                uid=uid,
                is_from_business=is_from_business,
                is_read=b'\\Seen' in flags,
                is_starred=b'\\Flagged' in flags,
                is_answered=b'\\Answered' in flags,
            )
            new_count += 1

        except Exception as e:
            logger.warning(f"Failed to process email {msg_num} in {folder_name}: {e}")
            continue

    return new_count


def sync_imap_messages(connection, max_messages: int = 500) -> int:
    """
    Sync messages from IMAP server for a given connection.
    Syncs both the configured folder (usually INBOX) and the Sent folder.

    Args:
        connection: EmailConnection model instance
        max_messages: Maximum number of messages to fetch per sync per folder

    Returns:
        Number of new messages synced
    """
    try:
        # Connect to IMAP
        if connection.imap_use_ssl:
            imap = imaplib.IMAP4_SSL(connection.imap_server, connection.imap_port, timeout=30)
        else:
            imap = imaplib.IMAP4(connection.imap_server, connection.imap_port)
            imap.starttls()

        imap.login(connection.username, connection.get_password())

        total_new_count = 0

        # Get all available folders
        result, folders_data = imap.list()
        if result == 'OK':
            folders_to_sync = []
            for folder_data in folders_data:
                if isinstance(folder_data, bytes):
                    decoded = folder_data.decode('utf-8', errors='replace')
                    # Extract folder name from response like: (\HasNoChildren) "/" "INBOX"
                    if '"' in decoded:
                        parts = decoded.split('"')
                        if len(parts) >= 2:
                            folder_name = parts[-2]
                            # Only skip Drafts (incomplete emails) and All Mail (duplicates)
                            skip_folders = ['Drafts', '[Gmail]/Drafts', '[Gmail]/All Mail']
                            if not any(skip.lower() == folder_name.lower() for skip in skip_folders):
                                folders_to_sync.append(folder_name)

            # Sync each folder
            for folder_name in folders_to_sync:
                try:
                    folder_count = _sync_folder(imap, connection, folder_name, max_messages)
                    total_new_count += folder_count
                    if folder_count > 0:
                        logger.info(f"Synced {folder_count} emails from {folder_name}")
                except Exception as e:
                    logger.warning(f"Failed to sync folder {folder_name}: {e}")
                    continue

        imap.logout()

        # Update connection status
        connection.last_sync_at = timezone.now()
        connection.last_sync_error = ''
        connection.save()

        logger.info(f"Synced {total_new_count} total new emails for {connection.email_address}")
        return total_new_count

    except Exception as e:
        logger.error(f"Email sync error for {connection.email_address}: {e}")
        connection.last_sync_error = str(e)
        connection.save()
        raise


def delete_emails_from_imap(connection, message_ids: List[str]) -> int:
    """
    Delete emails from IMAP server by moving them to Trash.

    Args:
        connection: EmailConnection model instance
        message_ids: List of Message-ID headers to delete

    Returns:
        Number of emails deleted
    """
    if not message_ids:
        return 0

    try:
        # Connect to IMAP
        if connection.imap_use_ssl:
            imap = imaplib.IMAP4_SSL(connection.imap_server, connection.imap_port, timeout=30)
        else:
            imap = imaplib.IMAP4(connection.imap_server, connection.imap_port)
            imap.starttls()

        imap.login(connection.username, connection.get_password())

        # Select folder (not readonly - we need to modify)
        result, data = imap.select(connection.sync_folder, readonly=False)
        if result != 'OK':
            raise Exception(f"Failed to select folder {connection.sync_folder}")

        deleted_count = 0

        for message_id in message_ids:
            try:
                # Search for message by Message-ID header
                # Note: Message-ID includes angle brackets, search needs them
                search_id = message_id if message_id.startswith('<') else f'<{message_id}>'
                result, data = imap.search(None, f'HEADER Message-ID "{search_id}"')

                if result != 'OK' or not data[0]:
                    # Try without angle brackets
                    clean_id = message_id.strip('<>')
                    result, data = imap.search(None, f'HEADER Message-ID "{clean_id}"')

                if result == 'OK' and data[0]:
                    msg_nums = data[0].split()
                    for msg_num in msg_nums:
                        # Mark as deleted
                        imap.store(msg_num, '+FLAGS', '\\Deleted')
                        deleted_count += 1

            except Exception as e:
                logger.warning(f"Failed to delete email {message_id}: {e}")
                continue

        # Expunge to permanently remove deleted messages
        imap.expunge()

        imap.close()
        imap.logout()

        logger.info(f"Deleted {deleted_count} emails from IMAP for {connection.email_address}")
        return deleted_count

    except Exception as e:
        logger.error(f"IMAP delete error for {connection.email_address}: {e}")
        raise


def move_email_to_folder(connection, message_id: str, source_folder: str, target_folder: str) -> bool:
    """
    Move an email from one IMAP folder to another.

    Args:
        connection: EmailConnection model instance
        message_id: Message-ID header of the email to move
        source_folder: Current folder of the email
        target_folder: Destination folder

    Returns:
        True if successful, False otherwise
    """
    try:
        # Connect to IMAP
        if connection.imap_use_ssl:
            imap = imaplib.IMAP4_SSL(connection.imap_server, connection.imap_port, timeout=30)
        else:
            imap = imaplib.IMAP4(connection.imap_server, connection.imap_port)
            imap.starttls()

        imap.login(connection.username, connection.get_password())

        # Select source folder
        result, data = imap.select(source_folder, readonly=False)
        if result != 'OK':
            raise Exception(f"Failed to select source folder {source_folder}")

        # Search for message by Message-ID
        search_id = message_id if message_id.startswith('<') else f'<{message_id}>'
        result, data = imap.search(None, f'HEADER Message-ID "{search_id}"')

        if result != 'OK' or not data[0]:
            # Try without angle brackets
            clean_id = message_id.strip('<>')
            result, data = imap.search(None, f'HEADER Message-ID "{clean_id}"')

        if result != 'OK' or not data[0]:
            logger.warning(f"Message {message_id} not found in {source_folder}")
            imap.logout()
            return False

        msg_nums = data[0].split()
        if not msg_nums:
            imap.logout()
            return False

        msg_num = msg_nums[0]

        # Copy to target folder
        result, data = imap.copy(msg_num, target_folder)
        if result != 'OK':
            raise Exception(f"Failed to copy message to {target_folder}")

        # Mark original as deleted
        imap.store(msg_num, '+FLAGS', '\\Deleted')

        # Expunge to remove the original
        imap.expunge()

        imap.close()
        imap.logout()

        logger.info(f"Moved email {message_id} from {source_folder} to {target_folder}")
        return True

    except Exception as e:
        logger.error(f"IMAP move error: {e}")
        return False


def get_available_folders(connection) -> List[Dict[str, Any]]:
    """
    Get list of available IMAP folders for a connection.

    Returns:
        List of folder info dicts with name and flags
    """
    try:
        if connection.imap_use_ssl:
            imap = imaplib.IMAP4_SSL(connection.imap_server, connection.imap_port, timeout=30)
        else:
            imap = imaplib.IMAP4(connection.imap_server, connection.imap_port)
            imap.starttls()

        imap.login(connection.username, connection.get_password())

        result, folders_data = imap.list()
        folders = []

        if result == 'OK':
            for folder_data in folders_data:
                if isinstance(folder_data, bytes):
                    decoded = folder_data.decode('utf-8', errors='replace')
                    if '"' in decoded:
                        parts = decoded.split('"')
                        if len(parts) >= 2:
                            folder_name = parts[-2]
                            # Skip Drafts and All Mail
                            skip_folders = ['Drafts', '[Gmail]/Drafts', '[Gmail]/All Mail']
                            if not any(skip.lower() == folder_name.lower() for skip in skip_folders):
                                folders.append({
                                    'name': folder_name,
                                    'display_name': folder_name.replace('[Gmail]/', '').replace('INBOX/', '')
                                })

        imap.logout()
        return folders

    except Exception as e:
        logger.error(f"Error getting folders: {e}")
        return []
