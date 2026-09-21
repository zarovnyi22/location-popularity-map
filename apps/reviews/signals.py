import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.locations.cache import bump_locations_cache_version
from apps.locations.models import LocationSubscription

from .models import Review

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Review)
def on_review_saved(sender, instance, created, **kwargs):
    # A review changes the location's average rating / reviews_count, which
    # are part of every cached locations-list page.
    bump_locations_cache_version()
    if created:
        _notify_new_review(instance)


@receiver(post_delete, sender=Review)
def on_review_deleted(sender, instance, **kwargs):
    bump_locations_cache_version()


def _notify_new_review(review):
    """Bonus: email the location's author, and everyone subscribed to the
    location, when a new review comes in."""
    location = review.location
    recipients = set()

    if location.author.email and location.author_id != review.author_id:
        recipients.add(location.author.email)

    subscriber_emails = (
        LocationSubscription.objects.filter(location=location)
        .exclude(user_id=review.author_id)
        .values_list("user__email", flat=True)
    )
    recipients.update(email for email in subscriber_emails if email)

    if not recipients:
        return

    send_mail(
        subject=f'Новий відгук про "{location.name}"',
        message=(
            f"{review.author.username} залишив(-ла) відгук ({review.rating}/5) "
            f'до локації "{location.name}":\n\n{review.comment}'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=list(recipients),
        fail_silently=True,
    )
