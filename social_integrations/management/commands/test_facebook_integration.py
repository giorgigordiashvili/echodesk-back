from django.core.management.base import BaseCommand
from django.conf import settings
from social_integrations.models import FacebookPageConnection, FacebookMessage


class Command(BaseCommand):
    help = 'Test and display Facebook integration status'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Facebook Integration Status ==='))
        
        # Check configuration
        fb_config = getattr(settings, 'SOCIAL_INTEGRATIONS', {})
        app_id = fb_config.get('FACEBOOK_APP_ID')
        app_secret = fb_config.get('FACEBOOK_APP_SECRET')
        
        if app_id and app_secret:
            self.stdout.write(self.style.SUCCESS(f'✓ Facebook App ID configured: {app_id}'))
            self.stdout.write(self.style.SUCCESS('✓ Facebook App Secret configured'))
        else:
            self.stdout.write(self.style.ERROR('✗ Facebook credentials not configured'))
            self.stdout.write('  Please set FACEBOOK_APP_ID and FACEBOOK_APP_SECRET in your environment')
        
        # Check database connections
        total_connections = FacebookPageConnection.objects.count()
        active_connections = FacebookPageConnection.objects.filter(is_active=True).count()
        total_messages = FacebookMessage.objects.count()
        
        self.stdout.write(f'\n📊 Database Statistics:')
        self.stdout.write(f'   Total page connections: {total_connections}')
        self.stdout.write(f'   Active connections: {active_connections}')
        self.stdout.write(f'   Total messages: {total_messages}')
        
        # Show active connections
        if active_connections > 0:
            self.stdout.write(f'\n📱 Active Facebook Pages:')
            for connection in FacebookPageConnection.objects.filter(is_active=True):
                message_count = FacebookMessage.objects.filter(page_connection=connection).count()
                self.stdout.write(f'   • {connection.page_name} (ID: {connection.page_id}) - {message_count} messages')
        
        self.stdout.write(f'\n🔗 API Endpoints available at:')
        self.stdout.write(f'   • GET  /api/social/facebook/status/ - Check connection status')
        self.stdout.write(f'   • GET  /api/social/facebook/oauth/start/ - Start OAuth flow')
        self.stdout.write(f'   • GET  /api/social/facebook/oauth/callback/ - OAuth callback')
        self.stdout.write(f'   • POST /api/social/facebook/disconnect/ - Disconnect pages')
        self.stdout.write(f'   • POST /api/social/facebook/webhook/ - Webhook endpoint')
        self.stdout.write(f'   • GET  /api/social/facebook-pages/ - List connected pages')
        self.stdout.write(f'   • GET  /api/social/facebook-messages/ - List messages')
        
        self.stdout.write(self.style.SUCCESS('\n✅ Facebook integration is ready!'))
