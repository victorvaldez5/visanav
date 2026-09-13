from django_filters.rest_framework import DjangoFilterBackend, FilterSet
from rest_framework import viewsets, filters
from rest_framework.permissions import AllowAny

from network.models import Organization
from network.serializers import OrganizationSerializer

class OrganizationFilter(FilterSet):
    class Meta:
        model = Organization
        fields = ["organization_type", "languages", "addresses__address__subdivision__name", "has_pro_bono"]


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = (AllowAny,)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter,]
    search_fields = ["name", "slug"]
    filterset_class = OrganizationFilter

    def get_queryset(self):
        return Organization.objects.all().prefetch_related("addresses", "addresses__address", "addresses__address__subdivision", "phone_numbers", "emails", "websites", "languages", "social_links", "attorneys")
