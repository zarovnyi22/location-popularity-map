from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.locations.models import Category, Location

from .models import Review, ReviewVote


class ReviewTestBase(APITestCase):
    def setUp(self):
        cache.clear()
        self.author = User.objects.create_user("nazar", password="pass12345")
        self.reviewer = User.objects.create_user("olena", password="pass12345")
        self.other_reviewer = User.objects.create_user("ihor", password="pass12345")
        category = Category.objects.create(name="Кав'ярні")
        self.location = Location.objects.create(
            name="Кав'ярня Аромат",
            category=category,
            author=self.author,
            address="вул. Шевченка, 1",
            latitude="49.842957",
            longitude="24.031111",
        )
        self.list_url = reverse("location-reviews", args=[self.location.pk])

    def review_url(self, review):
        return reverse("review-detail", args=[review.pk])

    def vote_url(self, review):
        return reverse("review-vote", args=[review.pk])


class ReviewCreateTests(ReviewTestBase):
    def test_authenticated_user_can_leave_review(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(self.list_url, {"rating": 5, "comment": "Чудове місце!"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(Review.objects.first().author, self.reviewer)

    def test_anonymous_cannot_leave_review(self):
        response = self.client.post(self.list_url, {"rating": 5, "comment": "Чудово"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rating_must_be_between_1_and_5(self):
        self.client.force_login(self.reviewer)
        response = self.client.post(self.list_url, {"rating": 6, "comment": "х"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        response = self.client.post(self.list_url, {"rating": 0, "comment": "х"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_one_review_per_user_per_location(self):
        self.client.force_login(self.reviewer)
        self.client.post(self.list_url, {"rating": 4, "comment": "Перший"})
        response = self.client.post(self.list_url, {"rating": 2, "comment": "Другий"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Review.objects.count(), 1)

    def test_only_author_can_edit_own_review(self):
        self.client.force_login(self.reviewer)
        self.client.post(self.list_url, {"rating": 4, "comment": "Перший"})
        review = Review.objects.first()

        self.client.force_login(self.other_reviewer)
        response = self.client.patch(self.review_url(review), {"comment": "Зламано"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_login(self.reviewer)
        response = self.client.patch(self.review_url(review), {"comment": "Виправлено"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ReviewVoteTests(ReviewTestBase):
    def setUp(self):
        super().setUp()
        self.review = Review.objects.create(location=self.location, author=self.reviewer, rating=5, comment="Супер")

    def test_authenticated_user_can_like(self):
        self.client.force_login(self.other_reviewer)
        response = self.client.post(self.vote_url(self.review), {"vote_type": "like"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["likes_count"], 1)

    def test_cannot_vote_same_way_twice(self):
        self.client.force_login(self.other_reviewer)
        self.client.post(self.vote_url(self.review), {"vote_type": "like"})
        response = self.client.post(self.vote_url(self.review), {"vote_type": "like"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ReviewVote.objects.count(), 1)

    def test_changing_vote_type_updates_existing_vote(self):
        self.client.force_login(self.other_reviewer)
        self.client.post(self.vote_url(self.review), {"vote_type": "like"})
        response = self.client.post(self.vote_url(self.review), {"vote_type": "dislike"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(ReviewVote.objects.count(), 1)
        self.assertEqual(ReviewVote.objects.first().vote_type, "dislike")

    def test_anonymous_cannot_vote(self):
        response = self.client.post(self.vote_url(self.review), {"vote_type": "like"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
