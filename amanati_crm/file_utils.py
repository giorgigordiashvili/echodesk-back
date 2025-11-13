"""
Utility functions for file handling.
"""

import re
import os
from datetime import datetime
from django.utils.deconstruct import deconstructible


def sanitize_filename(filename):
    """
    Sanitize filename to remove special characters that DigitalOcean Spaces rejects.
    Removes spaces, parentheses, and other special characters.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename with only alphanumeric, underscore, dot, and dash
    """
    # Get file extension
    name, ext = os.path.splitext(filename)

    # Sanitize the name: keep only alphanumeric, underscore, dot, and dash
    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', name)

    # Reconstruct filename
    return f"{safe_name}{ext}"


@deconstructible
class SanitizedUploadTo:
    """
    Deconstructible upload_to callable with filename sanitization.
    This is required for Django migrations to serialize the callable.
    """
    def __init__(self, base_path, date_based=True):
        self.base_path = base_path
        self.date_based = date_based

    def __call__(self, instance, filename):
        # Sanitize filename
        safe_filename = sanitize_filename(filename)

        # Build path
        if self.date_based:
            date_path = datetime.now().strftime('%Y/%m/%d')
            return f"{self.base_path}/{date_path}/{safe_filename}"
        else:
            return f"{self.base_path}/{safe_filename}"


def sanitized_upload_to(base_path, date_based=True):
    """
    Factory function to create upload_to callable with filename sanitization.

    Args:
        base_path: Base upload path (e.g., 'ticket_attachments')
        date_based: Whether to include date-based subdirectories (default: True)

    Returns:
        Deconstructible callable suitable for use in FileField/ImageField upload_to parameter

    Example:
        file = models.FileField(upload_to=sanitized_upload_to('attachments'))
        logo = models.ImageField(upload_to=sanitized_upload_to('logos', date_based=False))
    """
    return SanitizedUploadTo(base_path, date_based)
