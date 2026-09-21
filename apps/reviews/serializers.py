from django.contrib.auth.models import User
from rest_framework import serializers

from .models import Review, ReviewVote


class ReviewAuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class ReviewSerializer(serializers.ModelSerializer):
    author = ReviewAuthorSerializer(read_only=True)
    likes_count = serializers.IntegerField(read_only=True)
    dislikes_count = serializers.IntegerField(read_only=True)
    my_vote = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "location",
            "author",
            "rating",
            "comment",
            "created_at",
            "updated_at",
            "likes_count",
            "dislikes_count",
            "my_vote",
        ]
        read_only_fields = ["id", "location", "author", "created_at", "updated_at"]

    def get_my_vote(self, obj):
        # Prefer the prefetch from with_my_vote(); fall back to a single query.
        if hasattr(obj, "_user_votes"):
            return obj._user_votes[0].vote_type if obj._user_votes else None
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        vote = obj.votes.filter(user=request.user).first()
        return vote.vote_type if vote else None


class ReviewWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["id", "rating", "comment"]

    def validate(self, attrs):
        request = self.context["request"]
        location = self.context["location"]
        if self.instance is None and Review.objects.filter(location=location, author=request.user).exists():
            raise serializers.ValidationError(
                "Ви вже залишили відгук до цієї локації. Можна редагувати наявний відгук."
            )
        return attrs

    def create(self, validated_data):
        validated_data["location"] = self.context["location"]
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)


class ReviewVoteSerializer(serializers.Serializer):
    vote_type = serializers.ChoiceField(choices=ReviewVote.VOTE_CHOICES)
