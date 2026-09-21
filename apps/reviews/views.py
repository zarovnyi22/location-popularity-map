from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.locations.models import Location

from .models import Review, ReviewVote
from .permissions import IsAuthorOrAdminOrReadOnly
from .serializers import ReviewSerializer, ReviewVoteSerializer, ReviewWriteSerializer
from .services import annotate_vote_counts, with_my_vote


def _alive_reviews():
    """Reviews whose location is not soft-deleted."""
    return Review.objects.filter(location__is_deleted=False)


class ReviewListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/locations/<location_id>/reviews/"""

    permission_classes = [IsAuthorOrAdminOrReadOnly]

    def get_location(self):
        # Location.objects already excludes soft-deleted → 404 for deleted places.
        return get_object_or_404(Location, pk=self.kwargs["location_id"])

    def get_queryset(self):
        qs = _alive_reviews().filter(location_id=self.kwargs["location_id"]).select_related("author")
        qs = annotate_vote_counts(qs)
        return with_my_vote(qs, self.request.user)

    def get_serializer_class(self):
        return ReviewWriteSerializer if self.request.method == "POST" else ReviewSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["location"] = self.get_location()
        return context

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = serializer.save()
        except IntegrityError:
            return Response(
                {"detail": "Ви вже залишили відгук до цієї локації. Можна редагувати наявний відгук."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        review = with_my_vote(annotate_vote_counts(Review.objects.select_related("author")), request.user).get(
            pk=review.pk
        )
        return Response(
            ReviewSerializer(review, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )


class ReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/PATCH/DELETE /api/reviews/<pk>/"""

    permission_classes = [IsAuthorOrAdminOrReadOnly]

    def get_queryset(self):
        qs = _alive_reviews().select_related("author", "location")
        qs = annotate_vote_counts(qs)
        return with_my_vote(qs, self.request.user)

    def get_serializer_class(self):
        return ReviewWriteSerializer if self.request.method in ("PUT", "PATCH") else ReviewSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.request.method in ("PUT", "PATCH"):
            context["location"] = self.get_object().location
        return context

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        instance = self.get_queryset().get(pk=self.kwargs["pk"])
        return Response(ReviewSerializer(instance, context=self.get_serializer_context()).data)


class ReviewVoteView(APIView):
    """POST /api/reviews/<pk>/vote/ {"vote_type": "like"|"dislike"}
    DELETE /api/reviews/<pk>/vote/ — retract your own vote.

    One user may vote once per review; voting again with a different
    vote_type changes the existing vote instead of creating a second one.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        review = get_object_or_404(_alive_reviews(), pk=pk)
        serializer = ReviewVoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vote_type = serializer.validated_data["vote_type"]

        try:
            vote, created = ReviewVote.objects.get_or_create(
                review=review, user=request.user, defaults={"vote_type": vote_type}
            )
        except IntegrityError:
            vote = ReviewVote.objects.get(review=review, user=request.user)
            created = False

        if not created:
            if vote.vote_type == vote_type:
                return Response(
                    {"detail": "Ви вже голосували так само за цей відгук."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            vote.vote_type = vote_type
            vote.save(update_fields=["vote_type"])

        annotated = annotate_vote_counts(Review.objects.filter(pk=review.pk)).get()
        return Response(
            {
                "vote_type": vote.vote_type,
                "likes_count": annotated.likes_count,
                "dislikes_count": annotated.dislikes_count,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        review = get_object_or_404(_alive_reviews(), pk=pk)
        ReviewVote.objects.filter(review=review, user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
