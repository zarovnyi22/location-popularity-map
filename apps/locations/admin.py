from django.contrib import admin

from .models import Category, Location, LocationSubscription, LocationView


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "created_at"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "author", "is_deleted", "created_at"]
    list_filter = ["is_deleted", "category"]
    search_fields = ["name", "description", "address"]

    def get_queryset(self, request):
        # Show soft-deleted rows too, so staff can restore them.
        return Location.all_objects.select_related("category", "author")


@admin.register(LocationView)
class LocationViewAdmin(admin.ModelAdmin):
    list_display = ["location", "viewer_key", "user", "created_at"]
    list_filter = ["created_at"]


@admin.register(LocationSubscription)
class LocationSubscriptionAdmin(admin.ModelAdmin):
    list_display = ["location", "user", "created_at"]
