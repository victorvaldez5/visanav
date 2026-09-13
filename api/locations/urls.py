from rest_framework.routers import DefaultRouter

from .views import CountryViewSet, SubdivisionViewSet, AddressViewSet, LanguageViewSet

router = DefaultRouter()
router.register(r"countries", CountryViewSet, basename="countries")
router.register(r"subdivisions", SubdivisionViewSet, basename="subdivisions")

router.register(r"addresses", AddressViewSet, basename="addresses")
router.register(r"languages", LanguageViewSet, basename="languages")

urlpatterns = router.urls
