import csv

import pandas as pd
from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch
from django.http import HttpResponse, JsonResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .cache import build_locations_list_cache_key, bump_locations_cache_version
from .filters import LocationFilter
from .models import Category, Location, LocationSubscription
from .permissions import IsAdminOrReadOnly, IsAuthorOrAdminOrReadOnly
from .serializers import CategorySerializer, LocationSerializer, LocationWriteSerializer
from .services import annotate_rating_and_popularity, register_view_if_allowed


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = []  # small, static list — no filtering/search needed


class LocationViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthorOrAdminOrReadOnly]
    filterset_class = LocationFilter
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "rating", "popularity"]
    ordering = ["-created_at"]

    def get_queryset(self):
        qs = Location.objects.select_related("category", "author")
        qs = annotate_rating_and_popularity(qs)
        user = self.request.user
        if user and user.is_authenticated:
            qs = qs.prefetch_related(
                Prefetch(
                    "subscriptions",
                    queryset=LocationSubscription.objects.filter(user=user),
                    to_attr="_user_subscriptions",
                )
            )
        return qs

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return LocationWriteSerializer
        return LocationSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    # --- Caching on the public list endpoint -----------------------
    def list(self, request, *args, **kwargs):
        cache_key = build_locations_list_cache_key(
            request.query_params, request.user.id if request.user.is_authenticated else None
        )
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, timeout=settings.CACHE_TTL_LOCATIONS_LIST)
        return response

    # --- Soft delete --------------------------------------------------
    def perform_destroy(self, instance):
        instance.soft_delete()
        bump_locations_cache_version()

    def perform_create(self, serializer):
        serializer.save()
        bump_locations_cache_version()

    def perform_update(self, serializer):
        serializer.save()
        bump_locations_cache_version()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(self._read(serializer.instance), status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(self._read(serializer.instance))

    def _read(self, instance):
        """Re-fetch through the annotated queryset so rating/popularity are
        present, then serialize with the read serializer."""
        fresh = self.get_queryset().get(pk=instance.pk)
        return LocationSerializer(fresh, context=self.get_serializer_context()).data

    # --- View counter (rate-limited via Redis, see services.py) -------
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        register_view_if_allowed(instance, request)
        # Re-fetch so views_7d / popularity include the view we just wrote.
        return Response(self._read(instance))

    # --- Bonus: subscribe to a location's new reviews ------------------
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def subscribe(self, request, pk=None):
        location = self.get_object()
        LocationSubscription.objects.get_or_create(location=location, user=request.user)
        bump_locations_cache_version()
        return Response(status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def unsubscribe(self, request, pk=None):
        location = self.get_object()
        LocationSubscription.objects.filter(location=location, user=request.user).delete()
        bump_locations_cache_version()
        return Response(status=status.HTTP_204_NO_CONTENT)

    # --- Export ---------------------------------------------------------
    @action(detail=False, methods=["get"])
    def export(self, request):
        """GET /api/locations/export/?format=json|csv&scope=filtered|all

        scope=filtered (default) — applies whatever search/filter/ordering
        query params are also on the request (same ones the list endpoint
        understands), so "export what I'm currently looking at" works with
        no extra params when none were set.
        scope=all — ignores search/filter params entirely and exports every
        (non soft-deleted) location.
        """
        fmt = request.query_params.get("format", "json").lower()
        scope = request.query_params.get("scope", "filtered").lower()

        if scope not in ("filtered", "all"):
            return Response(
                {"detail": "Невідомий scope. Використайте ?scope=filtered або ?scope=all."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queryset = self.get_queryset() if scope == "all" else self.filter_queryset(self.get_queryset())

        rows = list(
            queryset.values(
                "id",
                "name",
                "description",
                "category__name",
                "address",
                "latitude",
                "longitude",
                "author__username",
                "created_at",
                "rating",
                "reviews_count",
                "views_7d",
                "popularity",
            )
        )

        if fmt == "csv":
            df = pd.DataFrame(rows)
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="locations.csv"'
            df.to_csv(response, index=False, quoting=csv.QUOTE_MINIMAL)
            return response

        if fmt == "json":
            return JsonResponse(rows, safe=False)

        return Response(
            {"detail": "Невідомий формат експорту. Використайте ?format=json або ?format=csv."},
            status=status.HTTP_400_BAD_REQUEST,
        )
