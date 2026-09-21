from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .managers import LocationAllManager, LocationManager


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # allow_unicode=True — кириличні назви мають давати нормальний slug, не "".
    slug = models.SlugField(max_length=120, unique=True, blank=True, allow_unicode=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            from uuid import uuid4

            base = slugify(self.name, allow_unicode=True) or f"category-{uuid4().hex[:8]}"
            candidate = base
            n = 2
            while Category.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
                candidate = f"{base}-{n}"
                n += 1
            self.slug = candidate
        super().save(*args, **kwargs)


class Location(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="locations"
    )
    address = models.CharField(max_length=500)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="locations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # --- Soft delete -------------------------------------------------
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = LocationManager()       # default: excludes soft-deleted rows
    all_objects = LocationAllManager()  # everything, including soft-deleted

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # Explicit names match 0001_initial so Django doesn't keep
            # "rename index" migrations around.
            models.Index(fields=["is_deleted"], name="locations_l_is_dele_1c2f4a_idx"),
            models.Index(fields=["category"], name="locations_l_categor_9d4e2b_idx"),
            models.Index(fields=["author"], name="locations_l_author__5e6f7a_idx"),
        ]

    def __str__(self):
        return self.name

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at"])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at"])


class LocationView(models.Model):
    """One row per counted view (rate-limited to 1/hour/viewer via Redis in
    services.py). Kept as raw history so "views in the last 7 days" can
    always be recomputed on demand instead of living in a stored counter."""

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="location_views",
    )
    # Identifies anonymous viewers (session key or IP) so the same
    # once-per-hour rule can apply to them too.
    viewer_key = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["location", "created_at"], name="locations_l_locatio_3a1b2c_idx"),
        ]

    def __str__(self):
        return f"view of {self.location_id} by {self.viewer_key} at {self.created_at}"


class LocationSubscription(models.Model):
    """Bonus feature: subscribe to a location to get emailed about new
    reviews."""

    location = models.ForeignKey(
        Location, on_delete=models.CASCADE, related_name="subscriptions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="location_subscriptions"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["location", "user"], name="unique_location_subscription"
            )
        ]

    def __str__(self):
        return f"{self.user_id} subscribed to {self.location_id}"
