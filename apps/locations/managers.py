from django.db import models


class LocationQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(is_deleted=False)

    def deleted(self):
        return self.filter(is_deleted=True)


class LocationManager(models.Manager):
    """Default manager: only "alive" (not soft-deleted) locations.

    Use Location.all_objects to reach everything, including soft-deleted rows
    (needed for the admin and for restoring a location).
    """

    def get_queryset(self):
        return LocationQuerySet(self.model, using=self._db).alive()


class LocationAllManager(models.Manager):
    def get_queryset(self):
        return LocationQuerySet(self.model, using=self._db)
