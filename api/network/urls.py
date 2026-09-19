from django.urls import path
from rest_framework import routers

from .views import (
    OrganizationViewSet,
    RepresentativeViewSet,
    OrganizationSubmissionCreateView,
)

router = routers.DefaultRouter()
router.register(r"organizations", OrganizationViewSet, basename="organization")
router.register(r"representatives", RepresentativeViewSet, basename="representative")

urlpatterns = router.urls + [
    path("submissions/", OrganizationSubmissionCreateView.as_view(), name="organization-submission"),
]
