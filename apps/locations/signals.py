from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import bump_locations_cache_version
from .models import Location


@receiver(post_save, sender=Location)
@receiver(post_delete, sender=Location)
def invalidate_locations_cache_on_location_change(sender, **kwargs):
    bump_locations_cache_version()


# Reviews also affect a location's rating/popularity in the cached list, so
# apps.reviews.signals calls bump_locations_cache_version() too (imported
# there directly to avoid a locations -> reviews -> locations import cycle).
