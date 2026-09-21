import django_filters as filters

from .models import Location


class LocationFilter(filters.FilterSet):
    category = filters.NumberFilter(field_name="category_id")
    category_slug = filters.CharFilter(field_name="category__slug")
    author = filters.NumberFilter(field_name="author_id")
    author_username = filters.CharFilter(field_name="author__username", lookup_expr="iexact")

    # `rating` is an ORM annotation (see services.annotate_rating_and_popularity),
    # not a model column — django-filter can still filter on it because the
    # annotation is already present on the queryset by the time this runs.
    rating_min = filters.NumberFilter(field_name="rating", lookup_expr="gte")
    rating_max = filters.NumberFilter(field_name="rating", lookup_expr="lte")

    class Meta:
        model = Location
        fields = ["category", "category_slug", "author", "author_username", "rating_min", "rating_max"]
