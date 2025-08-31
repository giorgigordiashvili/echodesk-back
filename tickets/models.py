from django.db import models
from django.conf import settings
import json


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


class TicketAssignment(models.Model):
    """Through model for ticket assignments with additional metadata."""
    ROLE_CHOICES = [
        ('primary', 'Primary Assignee'),
        ('collaborator', 'Collaborator'),
        ('reviewer', 'Reviewer'),
        ('observer', 'Observer'),
    ]
    
    ticket = models.ForeignKey('Ticket', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='collaborator')
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ticket_assignments_made'
    )
    
    class Meta:
        unique_together = [['ticket', 'user']]
        ordering = ['-assigned_at']
    
    def __str__(self):
        return f'{self.user.email} assigned to {self.ticket.title} as {self.role}'


class Ticket(models.Model):
    """Ticket model for managing support or internal CRM tickets."""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()  # Keep for backward compatibility
    rich_description = models.JSONField(
        null=True, 
        blank=True,
        help_text='Rich text content stored as JSON (Quill Delta format or HTML)'
    )
    description_format = models.CharField(
        max_length=20,
        choices=[
            ('plain', 'Plain Text'),
            ('html', 'HTML'),
            ('delta', 'Quill Delta'),
        ],
        default='plain',
        help_text='Format of the rich_description field'
    )
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
        blank=True,
        help_text='Primary assignee (for backward compatibility)'
    )
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='TicketAssignment',
        through_fields=('ticket', 'user'),
        related_name='tickets_assigned',
        blank=True,
        help_text='All users assigned to this ticket'
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


class SubTicketAssignment(models.Model):
    """Through model for sub-ticket assignments with additional metadata."""
    ROLE_CHOICES = [
        ('primary', 'Primary Assignee'),
        ('collaborator', 'Collaborator'),
        ('reviewer', 'Reviewer'),
        ('observer', 'Observer'),
    ]
    
    sub_ticket = models.ForeignKey('SubTicket', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='collaborator')
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sub_ticket_assignments_made'
    )
    
    class Meta:
        unique_together = [['sub_ticket', 'user']]
        ordering = ['-assigned_at']
    
    def __str__(self):
        return f'{self.user.email} assigned to {self.sub_ticket.title} as {self.role}'


class SubTicket(models.Model):
    """SubTicket model for creating hierarchical ticket relationships."""
    parent_ticket = models.ForeignKey(
        Ticket, 
        related_name='sub_tickets', 
        on_delete=models.CASCADE,
        help_text='Parent ticket that this sub-ticket belongs to'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    rich_description = models.JSONField(
        null=True, 
        blank=True,
        help_text='Rich text content stored as JSON'
    )
    description_format = models.CharField(
        max_length=20,
        choices=[
            ('plain', 'Plain Text'),
            ('html', 'HTML'),
            ('delta', 'Quill Delta'),
        ],
        default='plain'
    )
    
    # Sub-tickets inherit some properties from parent but can have their own
    priority = models.CharField(
        max_length=20, 
        choices=Ticket.PRIORITY_CHOICES, 
        default='medium'
    )
    is_completed = models.BooleanField(default=False)
    
    # Position for ordering sub-tickets within parent
    position = models.PositiveIntegerField(
        default=0,
        help_text='Position of sub-ticket within parent ticket'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='created_sub_tickets', 
        on_delete=models.CASCADE
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='assigned_sub_tickets', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text='Primary assignee (for backward compatibility)'
    )
    assigned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='SubTicketAssignment',
        through_fields=('sub_ticket', 'user'),
        related_name='sub_tickets_assigned',
        blank=True,
        help_text='All users assigned to this sub-ticket'
    )

    class Meta:
        ordering = ['position', 'created_at']

    def __str__(self):
        return f'{self.parent_ticket.title} -> {self.title}'

    def save(self, *args, **kwargs):
        # Auto-assign position if not set
        if not self.position:
            max_position = SubTicket.objects.filter(parent_ticket=self.parent_ticket).aggregate(
                models.Max('position')
            )['position__max'] or 0
            self.position = max_position + 1
        super().save(*args, **kwargs)


class ChecklistItem(models.Model):
    """Checklist items that can be embedded in ticket or sub-ticket descriptions."""
    # Can belong to either a ticket or sub-ticket
    ticket = models.ForeignKey(
        Ticket, 
        related_name='checklist_items', 
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    sub_ticket = models.ForeignKey(
        SubTicket, 
        related_name='checklist_items', 
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    text = models.TextField()
    is_checked = models.BooleanField(default=False)
    position = models.PositiveIntegerField(
        default=0,
        help_text='Position of checklist item'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE
    )

    class Meta:
        ordering = ['position', 'created_at']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(ticket__isnull=False, sub_ticket__isnull=True) |
                    models.Q(ticket__isnull=True, sub_ticket__isnull=False)
                ),
                name='checklist_item_belongs_to_ticket_or_sub_ticket'
            )
        ]

    def __str__(self):
        parent = self.ticket or self.sub_ticket
        status = "✓" if self.is_checked else "☐"
        return f'{status} {self.text} ({parent})'

    def save(self, *args, **kwargs):
        # Auto-assign position if not set
        if not self.position:
            if self.ticket:
                max_position = ChecklistItem.objects.filter(ticket=self.ticket).aggregate(
                    models.Max('position')
                )['position__max'] or 0
            else:
                max_position = ChecklistItem.objects.filter(sub_ticket=self.sub_ticket).aggregate(
                    models.Max('position')
                )['position__max'] or 0
            self.position = max_position + 1
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
