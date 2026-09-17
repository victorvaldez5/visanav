from rest_framework import routers

from .views import OrganizationViewSet, RepresentativeViewSet

router = routers.DefaultRouter()
router.register(r"organizations", OrganizationViewSet, basename="organization")
router.register(r"representatives", RepresentativeViewSet, basename="representative")

urlpatterns = router.urls
