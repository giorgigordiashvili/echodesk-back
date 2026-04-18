from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ContactSubmissionAdminViewSet,
    NewsletterSubscriberAdminViewSet,
    PublicTestimonialViewSet,
    TestimonialAdminViewSet,
    contact_submit,
    newsletter_subscribe,
    newsletter_unsubscribe,
)

# Public router — no auth, what the marketing site hits.
public_router = DefaultRouter()
public_router.register(
    r"testimonials",
    PublicTestimonialViewSet,
    basename="public-testimonial",
)

# Admin router — IsAdminUser gated.
admin_router = DefaultRouter()
admin_router.register(
    r"testimonials",
    TestimonialAdminViewSet,
    basename="admin-testimonial",
)
admin_router.register(
    r"contact-submissions",
    ContactSubmissionAdminViewSet,
    basename="admin-contact",
)
admin_router.register(
    r"newsletter-subscribers",
    NewsletterSubscriberAdminViewSet,
    basename="admin-newsletter",
)


urlpatterns = [
    path("public/", include(public_router.urls)),
    path(
        "public/contact/submit/",
        contact_submit,
        name="marketing-contact-submit",
    ),
    path(
        "public/newsletter/subscribe/",
        newsletter_subscribe,
        name="marketing-newsletter-subscribe",
    ),
    path(
        "public/newsletter/unsubscribe/<str:token>/",
        newsletter_unsubscribe,
        name="marketing-newsletter-unsubscribe",
    ),
    path("admin/", include(admin_router.urls)),
]
