import django_filters
from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from rest_framework import filters, viewsets
from rest_framework.permissions import AllowAny

from network.models import Organization, Representative
from network.serializers import OrganizationSerializer, RepresentativeSerializer


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
