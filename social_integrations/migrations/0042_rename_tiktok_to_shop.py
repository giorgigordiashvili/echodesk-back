# Migration: Rename TikTokCreatorAccount to TikTokShopAccount and update fields

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('social_integrations', '0041_autopostsettings_and_more'),
    ]

    operations = [
        # Step 1: Rename the model
        migrations.RenameModel(
            old_name='TikTokCreatorAccount',
            new_name='TikTokShopAccount',
        ),

        # Step 2: Remove old fields from TikTokShopAccount
        migrations.RemoveField(
            model_name='tiktokshopaccount',
            name='union_id',
        ),
        migrations.RemoveField(
            model_name='tiktokshopaccount',
            name='username',
        ),
        migrations.RemoveField(
            model_name='tiktokshopaccount',
            name='display_name',
        ),
        migrations.RemoveField(
            model_name='tiktokshopaccount',
            name='avatar_url',
        ),

        # Step 3: Add new fields to TikTokShopAccount
        migrations.AddField(
            model_name='tiktokshopaccount',
            name='seller_name',
            field=models.CharField(blank=True, help_text='Seller name from token response', max_length=200),
        ),
        migrations.AddField(
            model_name='tiktokshopaccount',
            name='seller_base_region',
            field=models.CharField(blank=True, help_text='Seller base region (e.g. GB)', max_length=10),
        ),
        migrations.AddField(
            model_name='tiktokshopaccount',
            name='shop_id',
            field=models.CharField(blank=True, help_text='Shop ID from webhook payloads', max_length=255),
        ),
        migrations.AddField(
            model_name='tiktokshopaccount',
            name='shop_cipher',
            field=models.CharField(blank=True, help_text='Shop cipher required for API calls', max_length=255),
        ),
        migrations.AddField(
            model_name='tiktokshopaccount',
            name='user_type',
            field=models.IntegerField(choices=[(0, 'Seller'), (1, 'Creator'), (3, 'Partner')], default=0, help_text='0=Seller, 1=Creator, 3=Partner'),
        ),
        migrations.AddField(
            model_name='tiktokshopaccount',
            name='refresh_token_expires_at',
            field=models.DateTimeField(blank=True, help_text='When the refresh token expires', null=True),
        ),

        # Step 4: Update TikTokMessage - rename FK field
        migrations.RenameField(
            model_name='tiktokmessage',
            old_name='creator_account',
            new_name='shop_account',
        ),

        # Step 5: Remove old fields from TikTokMessage
        migrations.RemoveField(
            model_name='tiktokmessage',
            name='sender_username',
        ),
        migrations.RemoveField(
            model_name='tiktokmessage',
            name='sender_display_name',
        ),
        migrations.RemoveField(
            model_name='tiktokmessage',
            name='sender_avatar_url',
        ),

        # Step 6: Add new fields to TikTokMessage
        migrations.AddField(
            model_name='tiktokmessage',
            name='index',
            field=models.CharField(blank=True, help_text='Message index for ordering', max_length=255),
        ),
        migrations.AddField(
            model_name='tiktokmessage',
            name='sender_role',
            field=models.CharField(blank=True, choices=[('BUYER', 'Buyer'), ('CUSTOMER_SERVICE', 'Customer Service'), ('SHOP', 'Shop'), ('SYSTEM', 'System'), ('ROBOT', 'Robot')], help_text='Role of the sender: BUYER, CUSTOMER_SERVICE, SHOP, SYSTEM, ROBOT', max_length=20),
        ),
        migrations.AddField(
            model_name='tiktokmessage',
            name='sender_im_user_id',
            field=models.CharField(blank=True, help_text='Internal CS participant ID', max_length=255),
        ),
        migrations.AddField(
            model_name='tiktokmessage',
            name='buyer_user_id',
            field=models.CharField(blank=True, help_text='Buyer user ID for querying orders', max_length=255),
        ),

        # Step 7: Update message_type field to use new choices
        migrations.AlterField(
            model_name='tiktokmessage',
            name='message_type',
            field=models.CharField(choices=[('TEXT', 'Text'), ('IMAGE', 'Image'), ('VIDEO', 'Video'), ('PRODUCT_CARD', 'Product Card'), ('ORDER_CARD', 'Order Card'), ('EMOTICONS', 'Emoticons'), ('COUPON_CARD', 'Coupon Card'), ('LOGISTICS_CARD', 'Logistics Card'), ('RETURN_REFUND_CARD', 'Return/Refund Card'), ('NOTIFICATION', 'Notification'), ('ALLOCATED_SERVICE', 'Allocated Service'), ('OTHER', 'Other')], default='TEXT', max_length=30),
        ),

        # Step 8: Update Meta options
        migrations.AlterModelOptions(
            name='tiktokshopaccount',
            options={'verbose_name': 'TikTok Shop Account', 'verbose_name_plural': 'TikTok Shop Accounts'},
        ),
    ]
