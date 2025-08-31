from django.contrib import admin
from django.utils.html import format_html
from .models import Ticket, Tag, TicketComment, TicketColumn


@admin.register(TicketColumn)
class TicketColumnAdmin(admin.ModelAdmin):
    """Admin configuration for TicketColumn model."""
    list_display = ('name', 'color_badge', 'position', 'is_default', 'is_closed_status', 'tickets_count', 'created_at')
    list_filter = ('is_default', 'is_closed_status', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('position', 'name')
    readonly_fields = ('created_at', 'updated_at', 'created_by')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'color', 'position')
        }),
        ('Status Settings', {
            'fields': ('is_default', 'is_closed_status')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def color_badge(self, obj):
        """Display color as a badge."""
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            obj.color, obj.color
        )
    color_badge.short_description = 'Color'
    
    def tickets_count(self, obj):
        """Display the number of tickets in this column."""
        count = obj.tickets.count()
        if count > 0:
            return format_html(
                '<a href="/admin/tickets/ticket/?column__id__exact={}">{} tickets</a>',
                obj.id, count
            )
        return '0 tickets'
    tickets_count.short_description = 'Tickets Count'
    
    def save_model(self, request, obj, form, change):
        """Set created_by to current user if creating new column."""
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin configuration for Tag model."""
    list_display = ('name', 'created_at', 'tickets_count')
    search_fields = ('name',)
    ordering = ('name',)
    readonly_fields = ('created_at',)

    def tickets_count(self, obj):
        """Display the number of tickets with this tag."""
        count = obj.tickets.count()
        if count > 0:
            return format_html(
                '<a href="/admin/tickets/ticket/?tags__id__exact={}">{} tickets</a>',
                obj.id, count
            )
        return '0 tickets'
    tickets_count.short_description = 'Tickets Count'


class TicketCommentInline(admin.TabularInline):
    """Inline admin for ticket comments."""
    model = TicketComment
    extra = 0
    readonly_fields = ('created_at', 'updated_at')
    fields = ('user', 'comment', 'created_at')

    def get_readonly_fields(self, request, obj=None):
        """Make user field readonly if editing existing comment."""
        if obj and obj.pk:
            return self.readonly_fields + ('user',)
        return self.readonly_fields


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    """Admin configuration for Ticket model."""
    list_display = (
        'title', 'status_badge', 'priority_badge', 'created_by', 
        'assigned_to', 'comments_count', 'created_at', 'updated_at'
    )
    list_filter = (
        'column', 'priority', 'created_at', 'updated_at', 
        'assigned_to', 'tags'
    )
    search_fields = (
        'title', 'description', 'created_by__email', 
        'created_by__first_name', 'created_by__last_name',
        'assigned_to__email', 'assigned_to__first_name', 
        'assigned_to__last_name'
    )
    raw_id_fields = ('created_by', 'assigned_to')
    filter_horizontal = ('tags',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'column', 'priority', 'position_in_column')
        }),
        ('Assignment', {
            'fields': ('created_by', 'assigned_to', 'tags')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    inlines = [TicketCommentInline]

    def status_badge(self, obj):
        """Display status with color coding."""
        if obj.column:
            return format_html(
                '<span style="background-color: {}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">{}</span>',
                obj.column.color, obj.column.name
            )
        return format_html(
            '<span style="color: #6c757d; font-style: italic;">No Status</span>'
        )
    status_badge.short_description = 'Status'

    def priority_badge(self, obj):
        """Display priority with color coding."""
        colors = {
            'low': '#28a745',       # Green
            'medium': '#ffc107',    # Yellow
            'high': '#fd7e14',      # Orange
            'critical': '#dc3545'   # Red
        }
        color = colors.get(obj.priority, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'

    def comments_count(self, obj):
        """Display the number of comments."""
        count = obj.comments.count()
        if count > 0:
            return format_html(
                '<span title="{} comments">{}</span>',
                count, count
            )
        return '0'
    comments_count.short_description = 'Comments'

    def get_queryset(self, request):
        """Optimize queries by prefetching related objects."""
        return super().get_queryset(request).select_related(
            'created_by', 'assigned_to'
        ).prefetch_related('tags', 'comments')

    def save_model(self, request, obj, form, change):
        """Set created_by to current user if creating new ticket."""
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    """Admin configuration for TicketComment model."""
    list_display = ('ticket_title', 'user', 'comment_preview', 'created_at')
    list_filter = ('created_at', 'ticket__column', 'ticket__priority')
    search_fields = (
        'comment', 'ticket__title', 'user__email',
        'user__first_name', 'user__last_name'
    )
    raw_id_fields = ('ticket', 'user')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('ticket', 'user', 'comment')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def ticket_title(self, obj):
        """Display ticket title with link."""
        return format_html(
            '<a href="/admin/tickets/ticket/{}/change/">{}</a>',
            obj.ticket.id, obj.ticket.title
        )
    ticket_title.short_description = 'Ticket'

    def comment_preview(self, obj):
        """Display a preview of the comment."""
        if len(obj.comment) > 50:
            return obj.comment[:47] + '...'
        return obj.comment
    comment_preview.short_description = 'Comment Preview'

    def get_queryset(self, request):
        """Optimize queries by selecting related objects."""
        return super().get_queryset(request).select_related('ticket', 'user')
