from django.core.management.base import BaseCommand
from tenants.models import Package, PricingModel


class Command(BaseCommand):
    help = 'Create initial packages based on the landing page pricing structure'
    
    def handle(self, *args, **options):
        self.stdout.write('Creating initial packages...')
        
        # Agent-based packages
        agent_packages = [
            {
                'name': 'essential',
                'display_name': 'Essential',
                'description': 'Basic ticket management and communication tools for small teams',
                'pricing_model': PricingModel.AGENT_BASED,
                'price_gel': 5,
                'max_whatsapp_messages': 1000,
                'max_storage_gb': 5,
                'ticket_management': True,
                'email_integration': True,
                'sip_calling': False,
                'facebook_integration': False,
                'instagram_integration': False,
                'whatsapp_integration': False,
                'advanced_analytics': False,
                'api_access': False,
                'custom_integrations': False,
                'priority_support': False,
                'dedicated_account_manager': False,
                'is_highlighted': False,
                'sort_order': 1
            },
            {
                'name': 'professional',
                'display_name': 'Professional',
                'description': 'Advanced features with SIP calling and social integrations',
                'pricing_model': PricingModel.AGENT_BASED,
                'price_gel': 15,
                'max_whatsapp_messages': 5000,
                'max_storage_gb': 15,
                'ticket_management': True,
                'email_integration': True,
                'sip_calling': True,
                'facebook_integration': True,
                'instagram_integration': True,
                'whatsapp_integration': False,
                'advanced_analytics': False,
                'api_access': False,
                'custom_integrations': False,
                'priority_support': True,
                'dedicated_account_manager': False,
                'is_highlighted': True,
                'sort_order': 2
            },
            {
                'name': 'enterprise',
                'display_name': 'Enterprise',
                'description': 'Complete omnichannel solution with WhatsApp and custom integrations',
                'pricing_model': PricingModel.AGENT_BASED,
                'price_gel': 25,
                'max_whatsapp_messages': 15000,
                'max_storage_gb': 50,
                'ticket_management': True,
                'email_integration': True,
                'sip_calling': True,
                'facebook_integration': True,
                'instagram_integration': True,
                'whatsapp_integration': True,
                'advanced_analytics': True,
                'api_access': True,
                'custom_integrations': True,
                'priority_support': True,
                'dedicated_account_manager': True,
                'is_highlighted': False,
                'sort_order': 3
            }
        ]
        
        # CRM-based packages
        crm_packages = [
            {
                'name': 'startup',
                'display_name': 'Startup',
                'description': 'Perfect for small businesses with up to 5 users',
                'pricing_model': PricingModel.CRM_BASED,
                'price_gel': 79,
                'max_users': 5,
                'max_whatsapp_messages': 2000,
                'max_storage_gb': 5,
                'ticket_management': True,
                'email_integration': True,
                'sip_calling': False,
                'facebook_integration': False,
                'instagram_integration': False,
                'whatsapp_integration': False,
                'advanced_analytics': False,
                'api_access': False,
                'custom_integrations': False,
                'priority_support': False,
                'dedicated_account_manager': False,
                'is_highlighted': False,
                'sort_order': 1
            },
            {
                'name': 'business',
                'display_name': 'Business',
                'description': 'Growing teams with advanced features and up to 25 users',
                'pricing_model': PricingModel.CRM_BASED,
                'price_gel': 249,
                'max_users': 25,
                'max_whatsapp_messages': 10000,
                'max_storage_gb': 50,
                'ticket_management': True,
                'email_integration': True,
                'sip_calling': True,
                'facebook_integration': True,
                'instagram_integration': True,
                'whatsapp_integration': False,
                'advanced_analytics': True,
                'api_access': False,
                'custom_integrations': False,
                'priority_support': True,
                'dedicated_account_manager': False,
                'is_highlighted': True,
                'sort_order': 2
            },
            {
                'name': 'corporate',
                'display_name': 'Corporate',
                'description': 'Large organizations with up to 100 users and enterprise features',
                'pricing_model': PricingModel.CRM_BASED,
                'price_gel': 699,
                'max_users': 100,
                'max_whatsapp_messages': 50000,
                'max_storage_gb': 500,
                'ticket_management': True,
                'email_integration': True,
                'sip_calling': True,
                'facebook_integration': True,
                'instagram_integration': True,
                'whatsapp_integration': True,
                'advanced_analytics': True,
                'api_access': True,
                'custom_integrations': True,
                'priority_support': True,
                'dedicated_account_manager': True,
                'is_highlighted': False,
                'sort_order': 3
            }
        ]
        
        # Create packages
        created_count = 0
        updated_count = 0
        
        for package_data in agent_packages + crm_packages:
            package, created = Package.objects.get_or_create(
                name=package_data['name'],
                defaults=package_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Created package: {package.display_name}')
                )
            else:
                # Update existing package
                for key, value in package_data.items():
                    setattr(package, key, value)
                package.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'Updated package: {package.display_name}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Package setup complete! Created: {created_count}, Updated: {updated_count}'
            )
        )
