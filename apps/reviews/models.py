from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Review(models.Model):
    location = models.ForeignKey(
        "locations.Location", on_delete=models.CASCADE, related_name="reviews"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["location", "author"], name="one_review_per_user_per_location"),
        ]

    def __str__(self):
        return f"{self.author_id} -> {self.location_id}: {self.rating}"


class ReviewVote(models.Model):
    LIKE = "like"
    DISLIKE = "dislike"
    VOTE_CHOICES = [(LIKE, "Like"), (DISLIKE, "Dislike")]

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_votes"
    )
    vote_type = models.CharField(max_length=7, choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["review", "user"], name="one_vote_per_user_per_review"),
        ]

    def __str__(self):
        return f"{self.user_id} {self.vote_type}d {self.review_id}"
