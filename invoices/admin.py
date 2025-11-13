from django.contrib import admin
from .models import InvoiceSettings, Invoice, InvoiceLineItem, InvoicePayment, InvoiceTemplate


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 1
    fields = ('description', 'quantity', 'unit', 'unit_price', 'tax_rate', 'discount_percent', 'position')


class InvoicePaymentInline(admin.TabularInline):
    model = InvoicePayment
    extra = 0
    fields = ('payment_date', 'amount', 'payment_method', 'reference_number')
    readonly_fields = ('payment_date',)


@admin.register(InvoiceSettings)
class InvoiceSettingsAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'tax_id', 'invoice_prefix', 'default_currency', 'updated_at')
    fieldsets = (
        ('Company Information', {
            'fields': ('company_name', 'tax_id', 'registration_number', 'address', 'phone', 'email', 'website')
        }),
        ('Branding', {
            'fields': ('logo', 'badge', 'signature')
        }),
        ('Invoice Configuration', {
            'fields': ('invoice_prefix', 'starting_number', 'default_currency', 'default_tax_rate', 'default_due_days')
        }),
        ('Bank Accounts', {
            'fields': ('bank_accounts',)
        }),
        ('Email Settings', {
            'fields': ('email_from', 'email_from_name', 'email_cc', 'email_subject_template', 'email_message_template')
        }),
        ('Footer & Terms', {
            'fields': ('footer_text', 'default_terms')
        }),
    )


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'client', 'status', 'issue_date', 'due_date', 'total', 'paid_amount', 'created_by')
    list_filter = ('status', 'issue_date', 'due_date', 'created_at')
    search_fields = ('invoice_number', 'client__first_name', 'client__last_name', 'client__email')
    readonly_fields = ('invoice_number', 'subtotal', 'tax_amount', 'total', 'paid_amount', 'uuid', 'created_at', 'updated_at')
    inlines = [InvoiceLineItemInline, InvoicePaymentInline]

    fieldsets = (
        ('Basic Information', {
            'fields': ('invoice_number', 'status', 'client', 'template')
        }),
        ('Dates', {
            'fields': ('issue_date', 'due_date', 'sent_date', 'paid_date')
        }),
        ('Financial Information', {
            'fields': ('currency', 'subtotal', 'tax_amount', 'discount_amount', 'total', 'paid_amount')
        }),
        ('Additional Information', {
            'fields': ('notes', 'terms_and_conditions')
        }),
        ('PDF', {
            'fields': ('pdf_file', 'pdf_generated_at')
        }),
        ('Metadata', {
            'fields': ('uuid', 'created_by', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by when creating
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InvoiceLineItem)
class InvoiceLineItemAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'description', 'quantity', 'unit_price', 'tax_rate', 'line_total')
    list_filter = ('item_source', 'created_at')
    search_fields = ('description', 'invoice__invoice_number')


@admin.register(InvoicePayment)
class InvoicePaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'payment_date', 'amount', 'payment_method', 'reference_number', 'recorded_by')
    list_filter = ('payment_method', 'payment_date')
    search_fields = ('invoice__invoice_number', 'reference_number')
    readonly_fields = ('created_at', 'updated_at')

    def save_model(self, request, obj, form, change):
        if not change:  # Only set recorded_by when creating
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InvoiceTemplate)
class InvoiceTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_default', 'is_active', 'created_by', 'created_at')
    list_filter = ('is_default', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'is_default', 'is_active')
        }),
        ('Template Content', {
            'fields': ('html_content', 'css_styles')
        }),
        ('Settings', {
            'fields': ('supported_languages',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # Only set created_by when creating
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
