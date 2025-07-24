from django.contrib import admin
from django.utils.html import format_html
from .models import Ticket, Tag, TicketComment


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
        'status', 'priority', 'created_at', 'updated_at', 
        'assigned_to', 'tags'
    )
    search_fields = (
        'title', 'description', 'created_by__username', 
        'created_by__first_name', 'created_by__last_name',
        'assigned_to__username', 'assigned_to__first_name', 
        'assigned_to__last_name'
    )
    raw_id_fields = ('created_by', 'assigned_to')
    filter_horizontal = ('tags',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'status', 'priority')
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
        colors = {
            'open': '#dc3545',      # Red
            'in_progress': '#ffc107', # Yellow
            'resolved': '#28a745',   # Green
            'closed': '#6c757d'      # Gray
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
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
    list_filter = ('created_at', 'ticket__status', 'ticket__priority')
    search_fields = (
        'comment', 'ticket__title', 'user__username',
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
