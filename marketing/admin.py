"""Django admin registrations for the marketing app.

Three sections:
  * ``Testimonial`` — simple CRUD with position/is_active list-edit.
  * ``ContactSubmission`` — read-only on the submission fields with
    bulk-action triage helpers (``mark_as_contacted``, ``close_won``,
    ``close_lost``).
  * ``NewsletterSubscriber`` — list + CSV export action.
"""

import csv

from django.contrib import admin, messages
from django.http import StreamingHttpResponse
from django.utils import timezone

from .models import ContactSubmission, NewsletterSubscriber, Testimonial


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = (
        "author_name", "company_name", "rating",
        "position", "is_active",
    )
    list_editable = ("position", "is_active")
    list_filter = ("is_active", "rating")
    search_fields = ("author_name", "company_name", "quote_ka", "quote_en")
    ordering = ("position",)
    fieldsets = (
        (None, {
            "fields": ("slug", "position", "is_active", "rating"),
        }),
        ("Author", {
            "fields": (
                "author_name", "author_role_ka", "author_role_en",
                "company_name", "logo_url", "avatar_url",
            ),
        }),
        ("Quote (multilingual)", {
            "fields": ("quote_ka", "quote_en"),
            "description": (
                "Write the primary Georgian quote in quote_ka. "
                "quote_en is optional — frontend falls back to KA."
            ),
        }),
    )


@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "name", "email", "company", "subject", "status", "created_at",
    )
    list_filter = ("status", "subject", "preferred_language", "created_at")
    search_fields = ("name", "email", "company", "message")
    readonly_fields = (
        "name", "email", "phone", "company",
        "subject", "message", "preferred_language",
        "referrer_url", "user_agent",
        "created_at", "updated_at",
    )
    fieldsets = (
        ("Submission (read-only)", {
            "fields": (
                "name", "email", "phone", "company",
                "subject", "message", "preferred_language",
                "referrer_url", "user_agent",
            ),
        }),
        ("Triage", {
            "fields": ("status", "handled_by", "handled_at", "internal_notes"),
        }),
        ("Audit", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
    actions = ("mark_as_contacted", "close_won", "close_lost")

    def _bulk_update_status(self, request, queryset, new_status, label):
        now = timezone.now()
        updated = 0
        for submission in queryset:
            submission.status = new_status
            submission.handled_at = submission.handled_at or now
            submission.handled_by = submission.handled_by or request.user
            submission.save(
                update_fields=["status", "handled_at", "handled_by", "updated_at"],
            )
            updated += 1
        self.message_user(
            request,
            f"Marked {updated} submission(s) as {label}.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Mark selected as contacted")
    def mark_as_contacted(self, request, queryset):
        self._bulk_update_status(request, queryset, "contacted", "contacted")

    @admin.action(description="Close selected as won")
    def close_won(self, request, queryset):
        self._bulk_update_status(request, queryset, "closed_won", "closed-won")

    @admin.action(description="Close selected as lost")
    def close_lost(self, request, queryset):
        self._bulk_update_status(request, queryset, "closed_lost", "closed-lost")


class _EchoBuffer:
    """Minimal file-like object for csv.writer → StreamingHttpResponse."""

    def write(self, value):
        return value


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ("email", "locale", "source", "is_active", "created_at")
    list_filter = ("is_active", "locale", "source")
    search_fields = ("email",)
    readonly_fields = ("unsubscribe_token", "created_at", "updated_at")
    actions = ("export_csv",)

    @admin.action(description="Export selected as CSV")
    def export_csv(self, request, queryset):
        writer = csv.writer(_EchoBuffer())
        header = ["email", "locale", "source", "created_at"]

        def rows():
            yield writer.writerow(header)
            for sub in queryset.iterator(chunk_size=500):
                yield writer.writerow([
                    sub.email,
                    sub.locale,
                    sub.source,
                    sub.created_at.isoformat(),
                ])

        response = StreamingHttpResponse(rows(), content_type="text/csv")
        response["Content-Disposition"] = (
            'attachment; filename="newsletter-subscribers.csv"'
        )
        return response
