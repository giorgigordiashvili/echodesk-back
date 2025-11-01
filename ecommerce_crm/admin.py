from django.contrib import admin
from .models import (
    Language,
    ProductCategory,
    ProductType,
    AttributeDefinition,
    ProductTypeAttribute,
    Product,
    ProductImage,
    ProductAttributeValue,
    ProductVariant,
    ProductVariantAttributeValue,
    EcommerceClient
)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ['code', '__str__', 'is_default', 'is_active', 'sort_order', 'created_at']
    list_filter = ['is_default', 'is_active']
    search_fields = ['code']
    ordering = ['sort_order', 'code']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Language Information', {
            'fields': ('code', 'name', 'sort_order')
        }),
        ('Settings', {
            'fields': ('is_default', 'is_active')
        }),
        ('System', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'slug', 'parent', 'sort_order', 'is_active', 'created_at']
    list_filter = ['is_active', 'parent']
    search_fields = ['slug']
    ordering = ['sort_order', 'id']


@admin.register(ProductType)
class ProductTypeAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'key', 'icon', 'sort_order', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['key']
    ordering = ['sort_order', 'id']


@admin.register(AttributeDefinition)
class AttributeDefinitionAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'key', 'attribute_type', 'is_required', 'is_variant_attribute', 'is_filterable', 'is_active']
    list_filter = ['attribute_type', 'is_required', 'is_variant_attribute', 'is_filterable', 'is_active']
    search_fields = ['key']
    ordering = ['sort_order', 'id']


@admin.register(ProductTypeAttribute)
class ProductTypeAttributeAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'product_type', 'attribute', 'is_required', 'sort_order', 'is_active']
    list_filter = ['product_type', 'is_required', 'is_active']
    search_fields = ['product_type__key', 'attribute__key']
    ordering = ['product_type', 'sort_order']


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ['image', 'alt_text', 'sort_order']


class ProductAttributeValueInline(admin.TabularInline):
    model = ProductAttributeValue
    extra = 0
    fields = ['attribute', 'value_text', 'value_number', 'value_boolean', 'value_date', 'value_json']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['sku', '__str__', 'product_type', 'category', 'price', 'quantity', 'status', 'is_featured', 'created_at']
    list_filter = ['product_type', 'category', 'status', 'is_featured', 'track_inventory']
    search_fields = ['sku', 'slug']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'created_by', 'updated_by']
    inlines = [ProductImageInline, ProductAttributeValueInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('sku', 'slug', 'name', 'description', 'short_description', 'product_type', 'category')
        }),
        ('Pricing', {
            'fields': ('price', 'compare_at_price', 'cost_price')
        }),
        ('Media', {
            'fields': ('image',)
        }),
        ('Inventory', {
            'fields': ('track_inventory', 'quantity', 'low_stock_threshold')
        }),
        ('Status & Metadata', {
            'fields': ('status', 'is_featured', 'weight', 'dimensions')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': ('created_at', 'updated_at', 'created_by', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['sku', '__str__', 'product', 'price', 'quantity', 'is_active', 'created_at']
    list_filter = ['is_active', 'product']
    search_fields = ['sku', 'product__sku']
    ordering = ['product', 'sort_order']


@admin.register(EcommerceClient)
class EcommerceClientAdmin(admin.ModelAdmin):
    list_display = ['email', 'full_name', 'phone_number', 'is_active', 'is_verified', 'last_login', 'created_at']
    list_filter = ['is_active', 'is_verified', 'created_at']
    search_fields = ['email', 'first_name', 'last_name', 'phone_number']
    ordering = ['-created_at']
    readonly_fields = ['created_at', 'updated_at', 'last_login']

    fieldsets = (
        ('Personal Information', {
            'fields': ('first_name', 'last_name', 'email', 'phone_number', 'date_of_birth')
        }),
        ('Authentication', {
            'fields': ('password',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_verified', 'last_login')
        }),
        ('System', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
