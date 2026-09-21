from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, LocationViewSet

router = DefaultRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("locations", LocationViewSet, basename="location")

urlpatterns = router.urls
