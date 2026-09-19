import django_filters
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from rest_framework import filters, generics, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle

from network.models import Organization, Representative, OrganizationSubmission
from network.serializers import (
    OrganizationSerializer,
    RepresentativeSerializer,
    OrganizationSubmissionSerializer,
)


class OrganizationFilter(FilterSet):
    # Region matches the address's subdivision name (e.g. "Arizona").
    region = django_filters.CharFilter(
        field_name="address__subdivision__name", lookup_expr="iexact"
    )
    # services/languages are arrays; match rows that contain the given value.
    service = django_filters.CharFilter(method="filter_service")
    language = django_filters.CharFilter(method="filter_language")

    class Meta:
        model = Organization
        fields = ["organization_type", "pro_bono", "fee_model"]

    def filter_service(self, queryset, name, value):
        return queryset.filter(services__contains=[value])

    def filter_language(self, queryset, name, value):
        return queryset.filter(languages__contains=[value])


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = (AllowAny,)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["name", "slug"]
    filterset_class = OrganizationFilter

    def get_queryset(self):
        # Contact details are on the row now; only the address is a join.
        return Organization.objects.filter(is_active=True).select_related(
            "address", "address__subdivision"
        )


class RepresentativeFilter(FilterSet):
    class Meta:
        model = Representative
        fields = ["provider_type", "organization", "dhs_only"]


class RepresentativeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RepresentativeSerializer
    permission_classes = (AllowAny,)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["name"]
    filterset_class = RepresentativeFilter

    def get_queryset(self):
        return Representative.objects.filter(is_active=True).select_related(
            "organization", "address", "address__subdivision"
        )


class OrganizationSubmissionCreateView(generics.CreateAPIView):
    """Public 'request to be included' intake from the marketing site.

    Create-only and open to anyone (AllowAny), but every submission lands as
    PENDING for admin review — nothing is auto-listed. Tighter throttle than the
    global default since it's an unauthenticated write endpoint."""

    queryset = OrganizationSubmission.objects.all()
    serializer_class = OrganizationSubmissionSerializer
    permission_classes = (AllowAny,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "submission"
