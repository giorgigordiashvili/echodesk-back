from rest_framework import serializers
from .models import (
    FacebookPageConnection, FacebookMessage,
    InstagramAccountConnection, InstagramMessage,
    WhatsAppBusinessAccount, WhatsAppMessage, WhatsAppMessageTemplate,
    WhatsAppContact, SocialIntegrationSettings,
    ChatAssignment, ChatRating,
    EmailConnection, EmailMessage, EmailDraft,
    TikTokCreatorAccount, TikTokMessage,
    EmailSignature, QuickReply,
    SocialClient, SocialClientCustomField, SocialClientCustomFieldValue, SocialAccount
)


class FacebookPageConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacebookPageConnection
        fields = ['id', 'page_id', 'page_name', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class FacebookMessageSerializer(serializers.ModelSerializer):
    page_id = serializers.CharField(source='page_connection.page_id', read_only=True)
    page_name = serializers.CharField(source='page_connection.page_name', read_only=True)
    reply_to_id = serializers.PrimaryKeyRelatedField(source='reply_to', read_only=True)

    class Meta:
        model = FacebookMessage
        fields = [
            'id', 'message_id', 'sender_id', 'sender_name', 'profile_pic_url', 'message_text',
            'attachment_type', 'attachment_url', 'attachments',
            'timestamp', 'is_from_page', 'is_delivered', 'delivered_at', 'is_read', 'read_at',
            'is_read_by_staff', 'read_by_staff_at',
            'page_id', 'page_name', 'created_at',
            # Reaction fields
            'reaction', 'reaction_emoji', 'reacted_by', 'reacted_at',
            # Reply fields
            'reply_to_message_id', 'reply_to_id'
        ]
        read_only_fields = ['id', 'is_delivered', 'delivered_at', 'is_read', 'read_at', 'created_at',
                           'reaction', 'reaction_emoji', 'reacted_by', 'reacted_at',
                           'reply_to_message_id', 'reply_to_id']


class FacebookSendMessageSerializer(serializers.Serializer):
    recipient_id = serializers.CharField(max_length=255, help_text="Facebook user ID to send message to")
    message = serializers.CharField(help_text="Message text to send")
    page_id = serializers.CharField(max_length=255, help_text="Facebook page ID to send from")
    reply_to_message_id = serializers.CharField(max_length=255, required=False, allow_blank=True, help_text="Message ID to reply to (optional)")


class InstagramAccountConnectionSerializer(serializers.ModelSerializer):
    facebook_page_name = serializers.CharField(source='facebook_page.page_name', read_only=True)

    class Meta:
        model = InstagramAccountConnection
        fields = [
            'id', 'instagram_account_id', 'username', 'profile_picture_url',
            'is_active', 'facebook_page_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InstagramMessageSerializer(serializers.ModelSerializer):
    account_id = serializers.CharField(source='account_connection.instagram_account_id', read_only=True)
    account_username = serializers.CharField(source='account_connection.username', read_only=True)

    class Meta:
        model = InstagramMessage
        fields = [
            'id', 'message_id', 'sender_id', 'sender_name', 'sender_username', 'sender_profile_pic',
            'message_text', 'attachment_type', 'attachment_url', 'attachments',
            'timestamp', 'is_from_business', 'is_delivered', 'delivered_at', 'is_read', 'read_at',
            'is_read_by_staff', 'read_by_staff_at',
            'account_id', 'account_username', 'created_at'
        ]
        read_only_fields = ['id', 'is_delivered', 'delivered_at', 'is_read', 'read_at', 'created_at']


class InstagramSendMessageSerializer(serializers.Serializer):
    recipient_id = serializers.CharField(max_length=255, help_text="Instagram user ID to send message to")
    message = serializers.CharField(help_text="Message text to send")
    instagram_account_id = serializers.CharField(max_length=255, help_text="Instagram account ID to send from")


class WhatsAppBusinessAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = WhatsAppBusinessAccount
        fields = [
            'id', 'waba_id', 'business_name', 'phone_number_id', 'phone_number',
            'display_phone_number', 'quality_rating', 'is_active',
            # Coexistence fields
            'coex_enabled', 'is_on_biz_app', 'platform_type', 'sync_status',
            'onboarded_at', 'contacts_synced_at', 'history_synced_at', 'throughput_limit',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'coex_enabled', 'is_on_biz_app', 'platform_type', 'sync_status',
            'onboarded_at', 'contacts_synced_at', 'history_synced_at', 'throughput_limit',
            'created_at', 'updated_at'
        ]


class WhatsAppMessageSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business_account.business_name', read_only=True)
    business_phone = serializers.CharField(source='business_account.display_phone_number', read_only=True)
    waba_id = serializers.CharField(source='business_account.waba_id', read_only=True)
    template_name = serializers.CharField(source='template.name', read_only=True, allow_null=True)

    class Meta:
        model = WhatsAppMessage
        fields = [
            'id', 'message_id', 'from_number', 'to_number', 'contact_name', 'profile_pic_url',
            'message_text', 'message_type', 'media_url', 'media_mime_type', 'attachments', 'timestamp',
            'is_from_business', 'status', 'is_delivered', 'delivered_at', 'is_read', 'read_at',
            'is_read_by_staff', 'read_by_staff_at',
            'error_message', 'business_name', 'business_phone', 'waba_id', 'template', 'template_name',
            'template_parameters',
            # Coexistence fields
            'source', 'is_echo', 'is_edited', 'edited_at', 'original_text', 'is_revoked', 'revoked_at',
            'created_at'
        ]
        read_only_fields = [
            'id', 'status', 'is_delivered', 'delivered_at', 'is_read', 'read_at',
            'source', 'is_echo', 'is_edited', 'edited_at', 'original_text', 'is_revoked', 'revoked_at',
            'created_at'
        ]


class WhatsAppSendMessageSerializer(serializers.Serializer):
    to_number = serializers.CharField(max_length=20, help_text="Recipient's phone number (E.164 format, e.g., +1234567890)")
    message = serializers.CharField(help_text="Message text to send")
    waba_id = serializers.CharField(max_length=100, help_text="WhatsApp Business Account ID to send from")

    def validate_to_number(self, value):
        """Ensure phone number starts with +"""
        if not value.startswith('+'):
            raise serializers.ValidationError("Phone number must be in E.164 format (start with +)")
        return value


class WhatsAppContactSerializer(serializers.ModelSerializer):
    """Serializer for WhatsApp contacts synced from Business App (Coexistence feature)"""
    account_phone = serializers.CharField(source='account.display_phone_number', read_only=True)
    account_name = serializers.CharField(source='account.business_name', read_only=True)

    class Meta:
        model = WhatsAppContact
        fields = [
            'id', 'account', 'wa_id', 'profile_name', 'is_business', 'contact_type',
            'synced_at', 'last_message_at', 'account_phone', 'account_name'
        ]
        read_only_fields = ['id', 'synced_at', 'account_phone', 'account_name']


class WhatsAppMessageTemplateSerializer(serializers.ModelSerializer):
    """Serializer for WhatsApp message templates"""
    business_name = serializers.CharField(source='business_account.business_name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True, allow_null=True)

    class Meta:
        model = WhatsAppMessageTemplate
        fields = [
            'id', 'business_account', 'template_id', 'name', 'language', 'status',
            'category', 'components', 'created_by', 'created_by_name', 'business_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'template_id', 'created_at', 'updated_at', 'business_name', 'created_by_name']


class WhatsAppTemplateCreateSerializer(serializers.Serializer):
    """Serializer for creating WhatsApp message templates"""
    waba_id = serializers.CharField(max_length=100, help_text="WhatsApp Business Account ID")
    name = serializers.CharField(
        max_length=512,
        help_text="Template name (lowercase, no spaces, use underscores)"
    )
    language = serializers.CharField(max_length=10, default='en', help_text="Language code (e.g., en, ka, ru)")
    category = serializers.ChoiceField(
        choices=['MARKETING', 'UTILITY', 'AUTHENTICATION'],
        default='UTILITY',
        help_text="Template category"
    )
    components = serializers.ListField(
        child=serializers.DictField(),
        help_text="Array of component objects (header, body, footer, buttons)"
    )

    def validate_name(self, value):
        """Validate template name format"""
        import re
        if not re.match(r'^[a-z0-9_]+$', value):
            raise serializers.ValidationError(
                "Template name must be lowercase alphanumeric with underscores only (no spaces)"
            )
        if len(value) < 1 or len(value) > 512:
            raise serializers.ValidationError("Template name must be 1-512 characters")
        return value

    def validate_components(self, value):
        """Validate components structure"""
        if not value:
            raise serializers.ValidationError("At least one component is required")

        # Check that at least one component is BODY
        has_body = any(comp.get('type') == 'BODY' for comp in value)
        if not has_body:
            raise serializers.ValidationError("Template must have at least one BODY component")

        return value


class WhatsAppTemplateSendSerializer(serializers.Serializer):
    """Serializer for sending template-based WhatsApp messages"""
    waba_id = serializers.CharField(max_length=100, help_text="WhatsApp Business Account ID")
    template_id = serializers.IntegerField(help_text="Template ID from database")
    to_number = serializers.CharField(
        max_length=20,
        help_text="Recipient's phone number (E.164 format, e.g., +1234567890)"
    )
    parameters = serializers.DictField(
        child=serializers.CharField(),
        required=False,
        allow_null=True,
        help_text="Template parameters as key-value pairs (e.g., {'name': 'John', 'order_id': '12345'})"
    )

    def validate_to_number(self, value):
        """Ensure phone number starts with +"""
        if not value.startswith('+'):
            raise serializers.ValidationError("Phone number must be in E.164 format (start with +)")
        return value


class SocialIntegrationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialIntegrationSettings
        fields = [
            'id', 'refresh_interval',
            'chat_assignment_enabled', 'session_management_enabled',
            'hide_assigned_chats', 'collect_customer_rating',
            'notification_sound_facebook', 'notification_sound_instagram',
            'notification_sound_whatsapp', 'notification_sound_email',
            'notification_sound_team_chat', 'notification_sound_system',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_refresh_interval(self, value):
        """Ensure refresh interval is within acceptable range"""
        if value < 1000:
            raise serializers.ValidationError("Refresh interval must be at least 1000ms (1 second)")
        if value > 60000:
            raise serializers.ValidationError("Refresh interval must be at most 60000ms (60 seconds)")
        return value


class ChatAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for chat assignments"""
    assigned_user_name = serializers.SerializerMethodField()
    assigned_user_email = serializers.SerializerMethodField()
    full_conversation_id = serializers.CharField(read_only=True)

    class Meta:
        model = ChatAssignment
        fields = [
            'id', 'platform', 'conversation_id', 'account_id', 'full_conversation_id',
            'assigned_user', 'assigned_user_name', 'assigned_user_email',
            'status', 'session_started_at', 'session_ended_at',
            'assigned_at', 'updated_at'
        ]
        read_only_fields = ['id', 'assigned_at', 'updated_at', 'full_conversation_id']

    def get_assigned_user_name(self, obj):
        if obj.assigned_user is None:
            return None
        return obj.assigned_user.get_full_name() or obj.assigned_user.email

    def get_assigned_user_email(self, obj):
        if obj.assigned_user is None:
            return None
        return obj.assigned_user.email


class ChatAssignmentCreateSerializer(serializers.Serializer):
    """Serializer for assigning a chat"""
    platform = serializers.ChoiceField(choices=['facebook', 'instagram', 'whatsapp', 'email'])
    conversation_id = serializers.CharField(max_length=255)
    account_id = serializers.CharField(max_length=255)


class ChatRatingSerializer(serializers.ModelSerializer):
    """Serializer for chat ratings"""
    assignment_id = serializers.IntegerField(source='assignment.id', read_only=True)
    platform = serializers.CharField(source='assignment.platform', read_only=True)
    conversation_id = serializers.CharField(source='assignment.conversation_id', read_only=True)

    class Meta:
        model = ChatRating
        fields = [
            'id', 'assignment', 'assignment_id', 'platform', 'conversation_id',
            'rating', 'rating_request_message_id', 'rating_response_message_id',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'assignment_id', 'platform', 'conversation_id']


# =============================================================================
# Email Serializers
# =============================================================================

class EmailConnectionSerializer(serializers.ModelSerializer):
    """Read-only serializer for email connections - NEVER exposes password"""

    class Meta:
        model = EmailConnection
        fields = [
            'id', 'email_address', 'display_name',
            'imap_server', 'imap_port', 'imap_use_ssl',
            'smtp_server', 'smtp_port', 'smtp_use_tls', 'smtp_use_ssl',
            'username', 'is_active',
            'last_sync_at', 'last_sync_error',
            'sync_folder', 'sync_days_back',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'last_sync_at', 'last_sync_error', 'created_at', 'updated_at']


class EmailConnectionCreateSerializer(serializers.Serializer):
    """Serializer for creating/updating email connections with password"""
    email_address = serializers.EmailField(help_text="Email address for this connection")
    display_name = serializers.CharField(max_length=200, required=False, allow_blank=True, help_text="Display name for sent emails")

    # IMAP settings
    imap_server = serializers.CharField(max_length=255, help_text="IMAP server hostname (e.g., imap.gmail.com)")
    imap_port = serializers.IntegerField(default=993, help_text="IMAP port (993 for SSL, 143 for STARTTLS)")
    imap_use_ssl = serializers.BooleanField(default=True, help_text="Use SSL for IMAP connection")

    # SMTP settings
    smtp_server = serializers.CharField(max_length=255, help_text="SMTP server hostname (e.g., smtp.gmail.com)")
    smtp_port = serializers.IntegerField(default=587, help_text="SMTP port (587 for STARTTLS, 465 for SSL)")
    smtp_use_tls = serializers.BooleanField(default=True, help_text="Use TLS/STARTTLS for SMTP")
    smtp_use_ssl = serializers.BooleanField(default=False, help_text="Use SSL for SMTP (alternative to TLS)")

    # Credentials
    username = serializers.CharField(max_length=255, help_text="Login username (usually email address)")
    password = serializers.CharField(max_length=500, write_only=True, help_text="Password or app password")

    # Sync settings
    sync_folder = serializers.CharField(max_length=100, default='INBOX', help_text="IMAP folder to sync")
    sync_days_back = serializers.IntegerField(default=30, min_value=0, max_value=3650, help_text="Number of days of history to sync (0 = all history)")

    def validate(self, data):
        """Validate that SMTP and IMAP settings are consistent"""
        # Can't use both TLS and SSL for SMTP
        if data.get('smtp_use_tls') and data.get('smtp_use_ssl'):
            raise serializers.ValidationError({
                'smtp_use_ssl': "Cannot use both TLS and SSL for SMTP. Choose one."
            })
        return data


class EmailMessageSerializer(serializers.ModelSerializer):
    """Serializer for email messages"""
    connection_id = serializers.IntegerField(source='connection.id', read_only=True)
    connection_email = serializers.EmailField(source='connection.email_address', read_only=True)
    connection_display_name = serializers.CharField(source='connection.display_name', read_only=True)

    class Meta:
        model = EmailMessage
        fields = [
            'id', 'message_id', 'thread_id', 'in_reply_to', 'references',
            'from_email', 'from_name', 'to_emails', 'cc_emails', 'bcc_emails', 'reply_to',
            'subject', 'body_text', 'body_html', 'attachments',
            'timestamp', 'folder', 'uid',
            'is_from_business', 'is_read', 'is_starred', 'is_answered', 'is_draft', 'labels',
            'is_read_by_staff', 'read_by_staff_at',
            'is_deleted', 'deleted_at',
            'connection_id', 'connection_email', 'connection_display_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'message_id', 'thread_id', 'in_reply_to', 'references',
            'timestamp', 'folder', 'uid',
            'is_from_business', 'is_answered',
            'connection_id', 'connection_email', 'connection_display_name',
            'created_at', 'updated_at'
        ]


class EmailSendSerializer(serializers.Serializer):
    """Serializer for sending email messages"""
    to_emails = serializers.ListField(
        child=serializers.EmailField(),
        min_length=1,
        help_text="List of recipient email addresses"
    )
    cc_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        allow_empty=True,
        help_text="List of CC email addresses"
    )
    bcc_emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        allow_empty=True,
        help_text="List of BCC email addresses"
    )
    subject = serializers.CharField(max_length=1000, required=False, allow_blank=True, help_text="Email subject")
    body_text = serializers.CharField(required=False, allow_blank=True, help_text="Plain text body")
    body_html = serializers.CharField(required=False, allow_blank=True, help_text="HTML body")
    reply_to_message_id = serializers.IntegerField(required=False, allow_null=True, help_text="ID of message being replied to")

    def validate(self, data):
        """Ensure at least one body is provided"""
        if not data.get('body_text') and not data.get('body_html'):
            raise serializers.ValidationError("At least one of body_text or body_html must be provided")
        return data


class EmailDraftSerializer(serializers.ModelSerializer):
    """Serializer for email drafts"""
    created_by_name = serializers.SerializerMethodField()
    reply_to_subject = serializers.CharField(source='reply_to_message.subject', read_only=True, allow_null=True)

    class Meta:
        model = EmailDraft
        fields = [
            'id', 'connection', 'to_emails', 'cc_emails', 'bcc_emails',
            'subject', 'body_text', 'body_html', 'attachments',
            'is_reply_all', 'is_forward',
            'reply_to_message', 'reply_to_subject',
            'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_by_name', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        return obj.created_by.get_full_name() or obj.created_by.email


class EmailMessageActionSerializer(serializers.Serializer):
    """Serializer for email message actions (star, read, label, move, delete)"""
    message_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        help_text="List of message IDs to perform action on"
    )
    thread_id = serializers.CharField(
        max_length=500,
        required=False,
        help_text="Thread ID to perform action on all messages in thread"
    )
    action = serializers.ChoiceField(
        choices=['mark_read', 'mark_unread', 'star', 'unstar', 'label', 'unlabel', 'move', 'delete', 'restore'],
        help_text="Action to perform"
    )
    # Optional parameters based on action
    label = serializers.CharField(max_length=100, required=False, help_text="Label name for label/unlabel actions")
    folder = serializers.CharField(max_length=100, required=False, help_text="Folder name for move action")

    def validate(self, data):
        action = data.get('action')
        # Either message_ids or thread_id must be provided
        if not data.get('message_ids') and not data.get('thread_id'):
            raise serializers.ValidationError("Either message_ids or thread_id must be provided")
        if action in ['label', 'unlabel'] and not data.get('label'):
            raise serializers.ValidationError({'label': f"Label is required for {action} action"})
        if action == 'move' and not data.get('folder'):
            raise serializers.ValidationError({'folder': "Folder is required for move action"})
        return data


class EmailFolderSerializer(serializers.Serializer):
    """Serializer for email folder information"""
    name = serializers.CharField(help_text="Folder name")
    delimiter = serializers.CharField(help_text="Folder hierarchy delimiter")
    flags = serializers.ListField(child=serializers.CharField(), help_text="IMAP folder flags")


# =============================================================================
# TikTok Serializers
# =============================================================================

class TikTokCreatorAccountSerializer(serializers.ModelSerializer):
    """Read-only serializer for TikTok creator accounts - NEVER exposes tokens"""

    class Meta:
        model = TikTokCreatorAccount
        fields = [
            'id', 'open_id', 'union_id', 'username', 'display_name', 'avatar_url',
            'scope', 'is_active', 'token_expires_at',
            'deactivated_at', 'deactivation_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'open_id', 'union_id', 'scope', 'token_expires_at',
            'deactivated_at', 'deactivation_reason',
            'created_at', 'updated_at'
        ]


class TikTokMessageSerializer(serializers.ModelSerializer):
    """Serializer for TikTok messages"""
    account_username = serializers.CharField(source='creator_account.username', read_only=True)
    account_display_name = serializers.CharField(source='creator_account.display_name', read_only=True)
    account_id = serializers.CharField(source='creator_account.open_id', read_only=True)

    class Meta:
        model = TikTokMessage
        fields = [
            'id', 'message_id', 'conversation_id',
            'sender_id', 'sender_username', 'sender_display_name', 'sender_avatar_url',
            'message_type', 'message_text', 'media_url', 'media_mime_type', 'attachments',
            'timestamp', 'is_from_creator',
            'is_delivered', 'delivered_at', 'is_read', 'read_at',
            'is_read_by_staff', 'read_by_staff_at',
            'error_message',
            'account_username', 'account_display_name', 'account_id',
            'created_at'
        ]
        read_only_fields = [
            'id', 'message_id', 'conversation_id',
            'sender_id', 'sender_username', 'sender_display_name', 'sender_avatar_url',
            'message_type', 'media_url', 'media_mime_type', 'attachments',
            'timestamp', 'is_from_creator',
            'is_delivered', 'delivered_at', 'is_read', 'read_at',
            'error_message',
            'account_username', 'account_display_name', 'account_id',
            'created_at'
        ]


class TikTokSendMessageSerializer(serializers.Serializer):
    """Serializer for sending TikTok messages"""
    conversation_id = serializers.CharField(
        max_length=255,
        help_text="Conversation ID (sender's open_id) to send message to"
    )
    message = serializers.CharField(help_text="Message text to send")
    message_type = serializers.ChoiceField(
        choices=['text', 'image', 'video'],
        default='text',
        help_text="Type of message to send"
    )
    media_url = serializers.URLField(
        required=False,
        allow_null=True,
        help_text="Media URL for image/video messages"
    )

    def validate(self, data):
        """Validate message content based on type"""
        msg_type = data.get('message_type', 'text')
        if msg_type == 'text' and not data.get('message'):
            raise serializers.ValidationError({'message': "Message text is required for text messages"})
        if msg_type in ('image', 'video') and not data.get('media_url'):
            raise serializers.ValidationError({'media_url': f"Media URL is required for {msg_type} messages"})
        return data


class TikTokStatusSerializer(serializers.Serializer):
    """Serializer for TikTok connection status response"""
    connected = serializers.BooleanField()
    account = TikTokCreatorAccountSerializer(allow_null=True)
    token_expires_at = serializers.DateTimeField(allow_null=True)
    is_token_expired = serializers.BooleanField()


class TikTokOAuthStartSerializer(serializers.Serializer):
    """Serializer for TikTok OAuth start response"""
    oauth_url = serializers.URLField(help_text="TikTok OAuth authorization URL")


# =============================================================================
# Email Signature Serializers
# =============================================================================

class EmailSignatureSerializer(serializers.ModelSerializer):
    """Serializer for email signature settings"""
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = EmailSignature
        fields = [
            'id', 'sender_name', 'signature_html', 'signature_text',
            'is_enabled', 'include_on_reply',
            'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_by_name', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None


# =============================================================================
# Quick Reply Serializers
# =============================================================================

class QuickReplySerializer(serializers.ModelSerializer):
    """Serializer for quick reply templates"""
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = QuickReply
        fields = [
            'id', 'title', 'message', 'platforms', 'shortcut',
            'category', 'use_count', 'position',
            'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'use_count', 'created_by', 'created_by_name', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None

    def validate_platforms(self, value):
        """Validate platforms list"""
        valid_platforms = {'all', 'facebook', 'instagram', 'whatsapp', 'email', 'tiktok'}
        if not value:
            return ['all']  # Default to all platforms
        for platform in value:
            if platform not in valid_platforms:
                raise serializers.ValidationError(
                    f"Invalid platform: {platform}. Valid options are: {', '.join(valid_platforms)}"
                )
        return value


class QuickReplyUseSerializer(serializers.Serializer):
    """Serializer for using a quick reply (replaces variables)"""
    customer_name = serializers.CharField(required=False, allow_blank=True, help_text="Customer display name")
    order_number = serializers.CharField(required=False, allow_blank=True, help_text="Most recent order number")
    agent_name = serializers.CharField(required=False, allow_blank=True, help_text="Current agent name")
    company_name = serializers.CharField(required=False, allow_blank=True, help_text="Company/business name")


class QuickReplyVariablesSerializer(serializers.Serializer):
    """Serializer for available quick reply variables"""
    name = serializers.CharField()
    description = serializers.CharField()


# =============================================================================
# Social Client Serializers
# =============================================================================

class SocialAccountSerializer(serializers.ModelSerializer):
    """Serializer for social accounts linked to a client"""

    class Meta:
        model = SocialAccount
        fields = [
            'id', 'platform', 'platform_id', 'account_connection_id',
            'display_name', 'username', 'profile_pic_url',
            'first_seen_at', 'last_seen_at', 'last_message_at',
            'is_auto_created'
        ]
        read_only_fields = ['id', 'first_seen_at', 'last_seen_at']


class SocialClientCustomFieldSerializer(serializers.ModelSerializer):
    """Serializer for custom field definitions"""
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SocialClientCustomField
        fields = [
            'id', 'name', 'label', 'field_type', 'is_required',
            'position', 'options', 'default_value', 'is_active',
            'created_by', 'created_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_by_name', 'created_at', 'updated_at']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None

    def validate_name(self, value):
        """Validate field name is snake_case"""
        import re
        if not re.match(r'^[a-z][a-z0-9_]*$', value):
            raise serializers.ValidationError(
                "Field name must be snake_case (lowercase letters, numbers, and underscores, starting with a letter)"
            )
        return value


class SocialClientCustomFieldValueSerializer(serializers.ModelSerializer):
    """Serializer for custom field values"""
    field_name = serializers.CharField(source='field.name', read_only=True)
    field_label = serializers.CharField(source='field.label', read_only=True)
    field_type = serializers.CharField(source='field.field_type', read_only=True)

    class Meta:
        model = SocialClientCustomFieldValue
        fields = ['id', 'field', 'field_name', 'field_label', 'field_type', 'value']
        read_only_fields = ['id', 'field_name', 'field_label', 'field_type']


class SocialClientSerializer(serializers.ModelSerializer):
    """Serializer for clients with nested social accounts and custom fields"""
    social_accounts = SocialAccountSerializer(many=True, read_only=True)
    custom_fields = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    booking_stats = serializers.SerializerMethodField()
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = SocialClient
        fields = [
            'id', 'name', 'email', 'phone', 'notes', 'profile_picture',
            'social_accounts', 'custom_fields',
            'created_by', 'created_by_name',
            'created_at', 'updated_at',
            # Booking fields
            'first_name', 'last_name', 'full_name',
            'is_booking_enabled', 'is_verified', 'last_login',
            'booking_stats',
        ]
        read_only_fields = [
            'id', 'created_by', 'created_by_name', 'created_at', 'updated_at',
            'social_accounts', 'booking_stats', 'full_name'
        ]

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.email
        return None

    def get_custom_fields(self, obj):
        """Return custom fields as a dict {field_name: value}"""
        values = obj.custom_field_values.select_related('field').all()
        return {v.field.name: v.value for v in values}

    def get_booking_stats(self, obj):
        """Return booking statistics for booking-enabled clients"""
        if not obj.is_booking_enabled:
            return None

        from django.utils import timezone
        today = timezone.now().date()

        # Import here to avoid circular import
        try:
            total = obj.bookings.count()
            completed = obj.bookings.filter(status='completed').count()
            upcoming = obj.bookings.filter(date__gte=today, status__in=['pending', 'confirmed']).count()
            return {
                'total': total,
                'completed': completed,
                'upcoming': upcoming
            }
        except Exception:
            return None


# Alias for backward compatibility
ClientSerializer = SocialClientSerializer


class SocialClientListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for client list (without all nested details)"""
    social_accounts_count = serializers.IntegerField(source='social_accounts.count', read_only=True)
    platforms = serializers.SerializerMethodField()
    booking_count = serializers.SerializerMethodField()
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = SocialClient
        fields = [
            'id', 'name', 'email', 'phone', 'profile_picture',
            'social_accounts_count', 'platforms',
            'created_at', 'updated_at',
            # Booking fields
            'first_name', 'last_name', 'full_name',
            'is_booking_enabled', 'is_verified',
            'booking_count',
        ]
        read_only_fields = fields

    def get_platforms(self, obj):
        """Return list of unique platforms linked to this client"""
        return list(obj.social_accounts.values_list('platform', flat=True).distinct())

    def get_booking_count(self, obj):
        """Return total booking count for booking-enabled clients"""
        if not obj.is_booking_enabled:
            return None
        try:
            return obj.bookings.count()
        except Exception:
            return None


# Alias for backward compatibility
ClientListSerializer = SocialClientListSerializer


class SocialClientCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating clients with custom fields and booking support"""
    custom_fields = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        help_text="Custom field values as {field_name: value}"
    )
    password = serializers.CharField(
        write_only=True,
        required=False,
        min_length=8,
        help_text="Password for booking authentication (only if is_booking_enabled=True)"
    )

    class Meta:
        model = SocialClient
        fields = [
            'name', 'email', 'phone', 'notes', 'profile_picture', 'custom_fields',
            # Booking fields
            'first_name', 'last_name', 'is_booking_enabled', 'password'
        ]

    def validate(self, attrs):
        # If enabling booking, require email and password
        is_booking_enabled = attrs.get('is_booking_enabled', False)
        if is_booking_enabled:
            if not attrs.get('email'):
                raise serializers.ValidationError({
                    'email': 'Email is required for booking-enabled clients'
                })
            # Password is only required on create when booking is enabled
            if not self.instance and not attrs.get('password'):
                raise serializers.ValidationError({
                    'password': 'Password is required for booking-enabled clients'
                })
        return attrs

    def create(self, validated_data):
        custom_fields_data = validated_data.pop('custom_fields', {})
        password = validated_data.pop('password', None)

        client = SocialClient.objects.create(**validated_data)

        # Set password if provided
        if password:
            client.set_password(password)
            client.generate_verification_token()
            client.save()

        # Create custom field values
        if custom_fields_data:
            self._save_custom_fields(client, custom_fields_data)

        return client

    def update(self, instance, validated_data):
        custom_fields_data = validated_data.pop('custom_fields', None)
        password = validated_data.pop('password', None)

        # Update basic fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Update password if provided
        if password:
            instance.set_password(password)

        instance.save()

        # Update custom fields if provided
        if custom_fields_data is not None:
            self._save_custom_fields(instance, custom_fields_data)

        return instance

    def _save_custom_fields(self, client, custom_fields_data):
        """Save custom field values for a client"""
        for field_name, value in custom_fields_data.items():
            try:
                field = SocialClientCustomField.objects.get(name=field_name, is_active=True)
                SocialClientCustomFieldValue.objects.update_or_create(
                    client=client,
                    field=field,
                    defaults={'value': value}
                )
            except SocialClientCustomField.DoesNotExist:
                pass  # Ignore unknown fields


# Alias for backward compatibility
ClientCreateSerializer = SocialClientCreateSerializer


class SocialAccountLinkSerializer(serializers.Serializer):
    """Serializer for linking/unlinking a social account to a client"""
    platform = serializers.ChoiceField(choices=['facebook', 'instagram', 'whatsapp', 'email', 'tiktok'])
    platform_id = serializers.CharField(max_length=255, help_text="Platform-specific ID (sender_id, wa_id, etc.)")
    account_connection_id = serializers.CharField(max_length=255, help_text="Account connection ID (page_id, waba_id, etc.)")
    display_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    username = serializers.CharField(max_length=255, required=False, allow_blank=True)
    profile_pic_url = serializers.URLField(max_length=500, required=False, allow_null=True, allow_blank=True)


class SocialClientByAccountSerializer(serializers.Serializer):
    """Serializer for get client by account response"""
    client = SocialClientSerializer(allow_null=True)
    social_account = SocialAccountSerializer(allow_null=True)
    found = serializers.BooleanField()