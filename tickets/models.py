from django.db import models
from django.conf import settings


class TicketColumn(models.Model):
    """Column model for organizing tickets in a Kanban-style board."""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    color = models.CharField(
        max_length=7, 
        default='#6B7280',
        help_text='Hex color code for the column (e.g., #3B82F6)'
    )
    position = models.PositiveIntegerField(
        default=0,
        help_text='Position of the column in the board (lower numbers appear first)'
    )
    is_default = models.BooleanField(
        default=False,
        help_text='Whether this is the default column for new tickets'
    )
    is_closed_status = models.BooleanField(
        default=False,
        help_text='Whether tickets in this column are considered closed/completed'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_columns'
    )

    class Meta:
        ordering = ['position', 'created_at']
        unique_together = [['name']]  # Ensure unique column names per tenant

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Ensure only one default column exists
        if self.is_default:
            TicketColumn.objects.filter(is_default=True).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)


class Tag(models.Model):
    """Tag model for categorizing tickets."""
    name = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Ticket(models.Model):
    """Ticket model for managing support or internal CRM tickets."""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    # Removed hardcoded status - now using dynamic columns
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    
    # Add column field for Kanban board organization
    column = models.ForeignKey(
        TicketColumn,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tickets',
        help_text='Column in which this ticket is placed on the Kanban board'
    )
    
    # Position within the column for drag-and-drop ordering
    position_in_column = models.PositiveIntegerField(
        default=0,
        help_text='Position of the ticket within its column'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='created_tickets', 
        on_delete=models.CASCADE
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='assigned_tickets', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='tickets')

    class Meta:
        ordering = ['column__position', 'position_in_column', '-created_at']

    def __str__(self):
        return self.title
    
    @property
    def status(self):
        """Get ticket status from its column."""
        return self.column.name.lower().replace(' ', '_') if self.column else 'unassigned'
    
    @property
    def is_closed(self):
        """Check if ticket is in a closed status column."""
        return self.column.is_closed_status if self.column else False

    def save(self, *args, **kwargs):
        # Auto-assign to default column if no column is set
        if not self.column_id:
            default_column = TicketColumn.objects.filter(is_default=True).first()
            if default_column:
                self.column = default_column
                
        # Auto-assign position in column if not set
        if self.column and not self.position_in_column:
            max_position = Ticket.objects.filter(column=self.column).aggregate(
                models.Max('position_in_column')
            )['position_in_column__max'] or 0
            self.position_in_column = max_position + 1
            
        super().save(*args, **kwargs)


class TicketComment(models.Model):
    """Comment model for ticket replies and updates."""
    ticket = models.ForeignKey(Ticket, related_name='comments', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Comment on {self.ticket.title} by {self.user.email}'
