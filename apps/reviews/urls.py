from django.urls import path

from . import views

urlpatterns = [
    path(
        "locations/<int:location_id>/reviews/",
        views.ReviewListCreateView.as_view(),
        name="location-reviews",
    ),
    path("reviews/<int:pk>/", views.ReviewDetailView.as_view(), name="review-detail"),
    path("reviews/<int:pk>/vote/", views.ReviewVoteView.as_view(), name="review-vote"),
]
