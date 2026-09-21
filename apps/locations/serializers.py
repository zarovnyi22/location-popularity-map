from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Category, Location, LocationSubscription


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug", "created_at"]
        read_only_fields = ["id", "slug", "created_at"]


class LocationAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class LocationSerializer(serializers.ModelSerializer):
    """Used for list/retrieve: exposes the computed rating/popularity that
    come from apps.locations.services.annotate_rating_and_popularity — they
    are queryset annotations, never stored fields."""

    author = LocationAuthorSerializer(read_only=True)
    category_detail = CategorySerializer(source="category", read_only=True)

    rating = serializers.FloatField(read_only=True)
    reviews_count = serializers.IntegerField(read_only=True)
    views_7d = serializers.IntegerField(read_only=True)
    popularity = serializers.FloatField(read_only=True)

    is_subscribed = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = [
            "id",
            "name",
            "description",
            "category",
            "category_detail",
            "address",
            "latitude",
            "longitude",
            "author",
            "created_at",
            "updated_at",
            "rating",
            "reviews_count",
            "views_7d",
            "popularity",
            "is_subscribed",
        ]
        read_only_fields = ["id", "author", "created_at", "updated_at"]

    def get_is_subscribed(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        # Prefetched on the viewset via Prefetch(..., to_attr="_user_subscriptions")
        # when available, to avoid one query per row; falls back to a query.
        cached = getattr(obj, "_user_subscriptions", None)
        if cached is not None:
            return len(cached) > 0
        return LocationSubscription.objects.filter(location=obj, user=request.user).exists()


class LocationWriteSerializer(serializers.ModelSerializer):
    """Separate from LocationSerializer because create/update must not
    accept the read-only computed fields or let the client set `author`."""

    class Meta:
        model = Location
        fields = [
            "id",
            "name",
            "description",
            "category",
            "address",
            "latitude",
            "longitude",
        ]

    def create(self, validated_data):
        request = self.context["request"]
        validated_data["author"] = request.user
        return super().create(validated_data)
