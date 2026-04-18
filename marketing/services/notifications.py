"""Email notifications for the marketing app.

SendGrid is already wired into Django's email backend
(``EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend'``,
``EMAIL_HOST='smtp.sendgrid.net'``, ``EMAIL_HOST_PASSWORD`` holds
the SendGrid API key), so we just use ``send_mail`` /
``EmailMultiAlternatives`` directly — no extra dependency needed.

Both helpers call ``fail_silently=True`` so a transient SMTP outage
never surfaces a 500 to the end user. Background monitoring
(Sentry) catches real delivery failures.
"""

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail

from ..models import ContactSubmission, NewsletterSubscriber


def notify_sales_team(submission: ContactSubmission) -> None:
    """Email the sales inbox whenever a new contact submission arrives."""

    subject = (
        f"[EchoDesk lead] {submission.get_subject_display()}: {submission.name}"
    )
    text_body = (
        f"New contact submission\n\n"
        f"Name: {submission.name}\n"
        f"Email: {submission.email}\n"
        f"Phone: {submission.phone or '—'}\n"
        f"Company: {submission.company or '—'}\n"
        f"Subject: {submission.get_subject_display()}\n"
        f"Language: {submission.preferred_language}\n"
        f"Referrer: {submission.referrer_url or '—'}\n\n"
        f"Message:\n{submission.message}\n\n"
        f"Admin: https://api.echodesk.ge/admin/marketing/"
        f"contactsubmission/{submission.id}/change/\n"
    )
    html_body = f"<pre>{text_body}</pre>"

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=(
            getattr(settings, "DEFAULT_FROM_EMAIL", None)
            or "no-reply@echodesk.ge"
        ),
        to=[getattr(settings, "SALES_EMAIL", "info@echodesk.ge")],
        reply_to=[submission.email],
    )
    msg.attach_alternative(html_body, "text/html")
    # We don't want form submissions to 500 if email is briefly down.
    msg.send(fail_silently=True)


def send_subscriber_welcome(sub: NewsletterSubscriber) -> None:
    """Confirmation + one-click-unsubscribe email for new subscribers."""

    site_url = getattr(settings, "SITE_URL", "https://echodesk.ge")
    unsubscribe_url = (
        f"{site_url}/api/marketing/public/newsletter/"
        f"unsubscribe/{sub.unsubscribe_token}/"
    )

    if sub.locale == "ka":
        subject = "EchoDesk | გამოწერა დადასტურდა"
        body = (
            f"მადლობა EchoDesk-ის ნიუსლეტერზე გამოწერისთვის.\n\n"
            f"ყოველი ახალი სტატიის გამოქვეყნებისას მიიღებ შეტყობინებას.\n\n"
            f"თუ გინდა გამოწერის გაუქმება: {unsubscribe_url}\n"
        )
    else:
        subject = "EchoDesk | Subscription confirmed"
        body = (
            f"Thanks for subscribing to EchoDesk updates.\n\n"
            f"We'll email you when there's a new post.\n\n"
            f"Unsubscribe any time: {unsubscribe_url}\n"
        )

    send_mail(
        subject,
        body,
        (
            getattr(settings, "DEFAULT_FROM_EMAIL", None)
            or "no-reply@echodesk.ge"
        ),
        [sub.email],
        fail_silently=True,
    )
