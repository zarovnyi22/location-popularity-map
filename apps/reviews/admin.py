from django.contrib import admin

from .models import Review, ReviewVote


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["location", "author", "rating", "created_at"]
    list_filter = ["rating"]
    search_fields = ["comment"]


@admin.register(ReviewVote)
class ReviewVoteAdmin(admin.ModelAdmin):
    list_display = ["review", "user", "vote_type", "created_at"]
    list_filter = ["vote_type"]
