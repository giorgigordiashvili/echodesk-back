"""
Celery tasks for ecommerce_crm app.
Handles asynchronous email sending for order lifecycle events.
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_order_email(self, schema_name, order_id, email_type):
    """
    Send order-related emails: confirmation, shipped, delivered.

    Args:
        schema_name: Tenant schema name for multi-tenant context
        order_id: Order ID to fetch
        email_type: One of 'confirmation', 'shipped', 'delivered'
    """
    from tenant_schemas.utils import schema_context

    try:
        with schema_context(schema_name):
            from .models import Order
            from .email_utils import send_email

            order = Order.objects.select_related(
                'client', 'delivery_address', 'shipping_method'
            ).prefetch_related('items__product').get(id=order_id)

            client = order.client
            items = order.items.all()

            # Build common context
            context = {
                'order': order,
                'order_number': order.order_number,
                'client_name': client.first_name or 'Valued Customer',
                'client_email': client.email,
                'items': [
                    {
                        'product_name': _get_product_name(item.product_name),
                        'quantity': item.quantity,
                        'price': item.price,
                        'subtotal': item.subtotal,
                    }
                    for item in items
                ],
                'subtotal': order.subtotal or order.total_amount,
                'shipping_cost': order.shipping_cost,
                'tax_amount': order.tax_amount,
                'discount_amount': order.discount_amount,
                'total_amount': order.total_amount,
            }

            if order.delivery_address:
                context['delivery_address'] = {
                    'label': order.delivery_address.label,
                    'address': order.delivery_address.address,
                    'city': order.delivery_address.city,
                }

            # Add store branding context
            try:
                from .models import EcommerceSettings
                store_settings = EcommerceSettings.objects.first()
                context['store_name'] = store_settings.store_name if store_settings and store_settings.store_name else 'Our Store'
                context['store_email'] = store_settings.store_email if store_settings and store_settings.store_email else ''
                context['store_phone'] = store_settings.store_phone if store_settings and store_settings.store_phone else ''
                context['store_logo'] = ''
                # Theme colors for email branding
                if store_settings:
                    context['theme_primary_color'] = store_settings.theme_primary_color or '221 83% 53%'
            except Exception:
                context['store_name'] = 'Our Store'
                context['store_email'] = ''
                context['store_phone'] = ''
                context['store_logo'] = ''
                context['theme_primary_color'] = '221 83% 53%'

            if email_type == 'confirmation':
                subject = f'Order Confirmed - {order.order_number}'
                template_name = 'order_confirmation'

            elif email_type == 'shipped':
                subject = f'Order Shipped - {order.order_number}'
                template_name = 'order_shipped'
                context['tracking_number'] = order.tracking_number
                context['courier_provider'] = order.courier_provider
                context['estimated_delivery_date'] = order.estimated_delivery_date

            elif email_type == 'delivered':
                subject = f'Order Delivered - {order.order_number}'
                template_name = 'order_delivered'

            else:
                logger.error(f'Unknown email type: {email_type}')
                return False

            success = send_email(
                subject=subject,
                recipient_email=client.email,
                template_name=template_name,
                context=context,
            )

            if success:
                logger.info(
                    f'Order {email_type} email sent for order {order.order_number} '
                    f'to {client.email}'
                )
            else:
                logger.warning(
                    f'Failed to send {email_type} email for order {order.order_number}'
                )

            return success

    except Exception as exc:
        logger.error(
            f'Error sending order {email_type} email for order_id={order_id}: {exc}'
        )
        raise self.retry(exc=exc)


def _get_product_name(product_name_field):
    """Extract a display name from a product_name JSONField."""
    if isinstance(product_name_field, dict):
        return product_name_field.get('en', next(iter(product_name_field.values()), 'Product'))
    return str(product_name_field)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_low_stock_products(self):
    """Daily check for low stock products - sends email to store admin."""
    from tenant_schemas.utils import schema_context
    from tenants.models import Tenant
    from django.db.models import F

    try:
        tenants = Tenant.objects.exclude(schema_name='public')

        for tenant in tenants:
            try:
                with schema_context(tenant.schema_name):
                    from .models import Product, EcommerceSettings
                    from .email_utils import send_email

                    low_stock = Product.objects.filter(
                        track_inventory=True,
                        quantity__lte=F('low_stock_threshold'),
                        status='active',
                    )

                    if not low_stock.exists():
                        continue

                    settings_obj = EcommerceSettings.objects.first()
                    if not settings_obj or not settings_obj.store_email:
                        logger.info(
                            f'Low stock products found for tenant {tenant.schema_name} '
                            f'but no store_email configured. Skipping.'
                        )
                        continue

                    products_list = []
                    for product in low_stock[:50]:  # Limit to 50 products per email
                        products_list.append({
                            'name': _get_product_name(product.name),
                            'sku': product.sku,
                            'quantity': product.quantity,
                            'threshold': product.low_stock_threshold,
                        })

                    context = {
                        'products': products_list,
                        'total_low_stock': low_stock.count(),
                        'store_name': settings_obj.store_name or 'Your Store',
                    }

                    success = send_email(
                        subject=f'Low Stock Alert - {len(products_list)} products need attention',
                        recipient_email=settings_obj.store_email,
                        template_name='low_stock_alert',
                        context=context,
                    )

                    if success:
                        logger.info(
                            f'Low stock alert sent for tenant {tenant.schema_name}: '
                            f'{low_stock.count()} products'
                        )
                    else:
                        logger.warning(
                            f'Failed to send low stock alert for tenant {tenant.schema_name}'
                        )

            except Exception as e:
                logger.error(
                    f'Error checking low stock for tenant {tenant.schema_name}: {e}'
                )
                continue

    except Exception as exc:
        logger.error(f'Error in check_low_stock_products task: {exc}')
        raise self.retry(exc=exc)
