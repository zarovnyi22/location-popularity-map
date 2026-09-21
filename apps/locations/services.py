"""Everything that must NOT become a stored column on Location:
rating, popularity, and the "1 view / user / hour" throttle.

Rating and popularity are pure ORM annotations computed on demand.
The view-throttle uses Redis (django.core.cache, backed by django-redis in
production, locmem in local dev/tests — see config/settings.py) as a short
TTL lock, independent of the CACHES backend used for list caching.
"""
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q
from django.db.models.functions import Coalesce
from django.conf import settings
from django.utils import timezone


def annotate_rating_and_popularity(queryset):
    """Attach `rating`, `reviews_count`, `views_7d` and `popularity` to a
    Location queryset. None of these exist as model fields — they are
    computed by the database on every query via Django ORM aggregation.
    """
    week_ago = timezone.now() - timedelta(days=7)

    queryset = queryset.annotate(
        rating=Coalesce(
            Avg("reviews__rating", output_field=FloatField()), 0.0, output_field=FloatField()
        ),
        reviews_count=Count("reviews", distinct=True),
        views_7d=Count(
            "views", filter=Q(views__created_at__gte=week_ago), distinct=True
        ),
    )
    queryset = queryset.annotate(
        popularity=ExpressionWrapper(
            F("rating") * settings.POPULARITY_RATING_WEIGHT
            + F("reviews_count") * settings.POPULARITY_REVIEWS_WEIGHT
            + F("views_7d") * settings.POPULARITY_VIEWS_WEIGHT,
            output_field=FloatField(),
        )
    )
    return queryset


def get_viewer_key(request):
    """A stable identifier for the once-per-hour view-counter throttle:
    the user id when authenticated, otherwise the session key (created if
    missing) so anonymous viewers are rate-limited too."""
    if request.user and request.user.is_authenticated:
        return f"user:{request.user.pk}"
    if not request.session.session_key:
        request.session.create()
    return f"session:{request.session.session_key}"


def register_view_if_allowed(location, request):
    """Increments `location`'s view count by writing a LocationView row,
    but only once per viewer per settings.VIEW_RATE_LIMIT_SECONDS. Returns
    True if a new view was registered, False if it was throttled.
    """
    from .models import LocationView  # local import: avoids a circular import

    viewer_key = get_viewer_key(request)
    lock_key = f"location_view:{location.pk}:{viewer_key}"

    # cache.add is atomic: it only succeeds if the key was not already set,
    # which is exactly the "once per hour" guarantee we need.
    was_set = cache.add(lock_key, 1, timeout=settings.VIEW_RATE_LIMIT_SECONDS)
    if not was_set:
        return False

    LocationView.objects.create(
        location=location,
        user=request.user if request.user.is_authenticated else None,
        viewer_key=viewer_key,
    )
    return True
