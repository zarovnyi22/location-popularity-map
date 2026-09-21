from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, Location, LocationView


def make_location(author, category, **kwargs):
    defaults = {
        "name": "Кав'ярня Аромат",
        "description": "Затишна кав'ярня в центрі",
        "address": "вул. Шевченка, 1",
        "latitude": "49.842957",
        "longitude": "24.031111",
    }
    defaults.update(kwargs)
    return Location.objects.create(author=author, category=category, **defaults)


class BaseAPITestCase(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("nazar", password="pass12345")
        self.other_user = User.objects.create_user("olena", password="pass12345")
        self.admin = User.objects.create_superuser("admin", password="pass12345", email="admin@example.com")
        self.category = Category.objects.create(name="Кав'ярні")


class CategoryTests(BaseAPITestCase):
    def test_anyone_can_list_categories(self):
        response = self.client.get(reverse("category-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_only_staff_can_create_category(self):
        response = self.client.post(reverse("category-list"), {"name": "Парки"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_login(self.admin)
        response = self.client.post(reverse("category-list"), {"name": "Парки"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class LocationCRUDTests(BaseAPITestCase):
    def test_anonymous_can_list_and_retrieve(self):
        location = make_location(self.user, self.category)
        response = self.client.get(reverse("location-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        response = self.client.get(reverse("location-detail", args=[location.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_cannot_create(self):
        response = self.client.post(
            reverse("location-list"),
            {
                "name": "Test",
                "category": self.category.pk,
                "address": "addr",
                "latitude": "1.0",
                "longitude": "1.0",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authenticated_user_can_create_and_is_set_as_author(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("location-list"),
            {
                "name": "Нова локація",
                "description": "опис",
                "category": self.category.pk,
                "address": "addr",
                "latitude": "1.000000",
                "longitude": "1.000000",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        location = Location.objects.get(pk=response.data["id"])
        self.assertEqual(location.author, self.user)

    def test_only_author_or_admin_can_update(self):
        location = make_location(self.user, self.category)

        self.client.force_login(self.other_user)
        response = self.client.patch(reverse("location-detail", args=[location.pk]), {"name": "Hacked"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_login(self.user)
        response = self.client.patch(reverse("location-detail", args=[location.pk]), {"name": "Оновлено"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_update_others_location(self):
        location = make_location(self.user, self.category)
        self.client.force_login(self.admin)
        response = self.client.patch(reverse("location-detail", args=[location.pk]), {"name": "Адмін поправив"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_soft_delete(self):
        location = make_location(self.user, self.category)
        self.client.force_login(self.user)
        response = self.client.delete(reverse("location-detail", args=[location.pk]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Gone from the default manager / API...
        self.assertFalse(Location.objects.filter(pk=location.pk).exists())
        response = self.client.get(reverse("location-detail", args=[location.pk]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # ...but still present in the database.
        raw = Location.all_objects.get(pk=location.pk)
        self.assertTrue(raw.is_deleted)
        self.assertIsNotNone(raw.deleted_at)

    def test_only_author_or_admin_can_delete(self):
        location = make_location(self.user, self.category)
        self.client.force_login(self.other_user)
        response = self.client.delete(reverse("location-detail", args=[location.pk]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class LocationFilterSearchOrderTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.cat_cafe = self.category
        self.cat_park = Category.objects.create(name="Парки")
        self.loc_a = make_location(self.user, self.cat_cafe, name="Кав'ярня Аромат")
        self.loc_b = make_location(self.other_user, self.cat_park, name="Стрийський парк")

    def test_filter_by_category(self):
        response = self.client.get(reverse("location-list"), {"category": self.cat_park.pk})
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.loc_b.pk])

    def test_filter_by_author(self):
        response = self.client.get(reverse("location-list"), {"author": self.user.pk})
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.loc_a.pk])

    def test_search_by_name(self):
        response = self.client.get(reverse("location-list"), {"search": "парк"})
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.loc_b.pk])

    def test_ordering_by_created_at(self):
        response = self.client.get(reverse("location-list"), {"ordering": "created_at"})
        ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(ids, [self.loc_a.pk, self.loc_b.pk])

    def test_pagination_default_page_size(self):
        for i in range(15):
            make_location(self.user, self.cat_cafe, name=f"Локація {i}")
        response = self.client.get(reverse("location-list"))
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["next"])


class RatingPopularityTests(BaseAPITestCase):
    def test_rating_is_average_of_reviews_and_not_stored(self):
        from apps.reviews.models import Review

        location = make_location(self.user, self.category)
        Review.objects.create(location=location, author=self.user, rating=5, comment="Супер")
        Review.objects.create(location=location, author=self.other_user, rating=3, comment="Норм")

        self.assertNotIn("rating", [f.name for f in Location._meta.get_fields()])

        response = self.client.get(reverse("location-detail", args=[location.pk]))
        self.assertEqual(response.data["rating"], 4.0)
        self.assertEqual(response.data["reviews_count"], 2)

    def test_location_with_no_reviews_has_zero_rating(self):
        location = make_location(self.user, self.category)
        response = self.client.get(reverse("location-detail", args=[location.pk]))
        self.assertEqual(response.data["rating"], 0)
        self.assertEqual(response.data["reviews_count"], 0)


class ViewCounterTests(BaseAPITestCase):
    def test_view_is_counted_once_per_hour_per_user(self):
        location = make_location(self.user, self.category)
        self.client.force_login(self.other_user)

        self.client.get(reverse("location-detail", args=[location.pk]))
        self.client.get(reverse("location-detail", args=[location.pk]))
        self.client.get(reverse("location-detail", args=[location.pk]))

        self.assertEqual(LocationView.objects.filter(location=location).count(), 1)

    def test_different_users_each_count_a_view(self):
        location = make_location(self.user, self.category)

        self.client.force_login(self.user)
        self.client.get(reverse("location-detail", args=[location.pk]))

        self.client.force_login(self.other_user)
        self.client.get(reverse("location-detail", args=[location.pk]))

        self.assertEqual(LocationView.objects.filter(location=location).count(), 2)


class ExportTests(BaseAPITestCase):
    def test_export_json(self):
        make_location(self.user, self.category)
        response = self.client.get(reverse("location-export"), {"format": "json"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_export_csv(self):
        make_location(self.user, self.category)
        response = self.client.get(reverse("location-export"), {"format": "csv"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "text/csv")

    def test_export_unknown_format(self):
        response = self.client.get(reverse("location-export"), {"format": "xml"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_scope_filtered_applies_query_params(self):
        cat_park = Category.objects.create(name="Парки")
        make_location(self.user, self.category, name="Кав'ярня Аромат")
        make_location(self.user, cat_park, name="Стрийський парк")

        response = self.client.get(
            reverse("location-export"), {"format": "json", "category": self.category.pk}
        )
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Кав'ярня Аромат")

    def test_export_scope_all_ignores_filters(self):
        cat_park = Category.objects.create(name="Парки")
        make_location(self.user, self.category, name="Кав'ярня Аромат")
        make_location(self.user, cat_park, name="Стрийський парк")

        response = self.client.get(
            reverse("location-export"),
            {"format": "json", "category": self.category.pk, "scope": "all"},
        )
        data = response.json()
        self.assertEqual(len(data), 2)

    def test_export_unknown_scope(self):
        response = self.client.get(reverse("location-export"), {"scope": "everything"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class CacheInvalidationTests(BaseAPITestCase):
    def test_list_cache_is_invalidated_after_create(self):
        response = self.client.get(reverse("location-list"))
        self.assertEqual(len(response.data["results"]), 0)

        self.client.force_login(self.user)
        self.client.post(
            reverse("location-list"),
            {
                "name": "Нова локація",
                "category": self.category.pk,
                "address": "addr",
                "latitude": "1.000000",
                "longitude": "1.000000",
            },
        )

        response = self.client.get(reverse("location-list"))
        self.assertEqual(len(response.data["results"]), 1)

    def test_subscribe_invalidates_list_cache_for_is_subscribed(self):
        location = make_location(self.user, self.category)
        self.client.force_login(self.other_user)

        # Warm the per-user list cache with is_subscribed=false.
        response = self.client.get(reverse("location-list"))
        self.assertFalse(response.data["results"][0]["is_subscribed"])

        self.client.post(reverse("location-subscribe", args=[location.pk]))

        response = self.client.get(reverse("location-list"))
        self.assertTrue(response.data["results"][0]["is_subscribed"])


class SoftDeleteReviewAccessTests(BaseAPITestCase):
    def test_reviews_of_soft_deleted_location_are_hidden(self):
        location = make_location(self.user, self.category)
        from apps.reviews.models import Review

        review = Review.objects.create(
            location=location, author=self.other_user, rating=4, comment="ok"
        )
        self.client.force_login(self.user)
        self.client.delete(reverse("location-detail", args=[location.pk]))

        response = self.client.get(reverse("review-detail", args=[review.pk]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("review-vote", args=[review.pk]), {"vote_type": "like"}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CategorySlugTests(BaseAPITestCase):
    def test_cyrillic_name_gets_non_empty_slug(self):
        cat = Category.objects.create(name="Музеї")
        self.assertTrue(cat.slug)
        self.assertIn("музе", cat.slug)

    def test_similar_names_get_unique_slugs(self):
        a = Category.objects.create(name="Кав'ярні-центр")
        b = Category.objects.create(name="Кавярні-центр")
        # Both slugify to something non-empty and must not collide.
        self.assertTrue(a.slug)
        self.assertTrue(b.slug)
        self.assertNotEqual(a.slug, b.slug)


class RetrieveViewCountTests(BaseAPITestCase):
    def test_retrieve_response_includes_new_view(self):
        location = make_location(self.user, self.category)
        self.client.force_login(self.user)
        response = self.client.get(reverse("location-detail", args=[location.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["views_7d"], 1)
        self.assertGreater(response.data["popularity"], 0)
