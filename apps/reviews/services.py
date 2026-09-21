"""ORM helpers for reviews — keep vote counters off the model columns."""
from django.db.models import Count, Prefetch, Q

from .models import ReviewVote


def annotate_vote_counts(queryset):
    """Attach likes_count / dislikes_count as annotations (one query, no N+1)."""
    return queryset.annotate(
        likes_count=Count(
            "votes",
            filter=Q(votes__vote_type=ReviewVote.LIKE),
            distinct=True,
        ),
        dislikes_count=Count(
            "votes",
            filter=Q(votes__vote_type=ReviewVote.DISLIKE),
            distinct=True,
        ),
    )


def with_my_vote(queryset, user):
    """Prefetch only the current user's vote into `_user_votes` (0 or 1 row)."""
    if not user or not user.is_authenticated:
        return queryset
    return queryset.prefetch_related(
        Prefetch(
            "votes",
            queryset=ReviewVote.objects.filter(user=user),
            to_attr="_user_votes",
        )
    )
