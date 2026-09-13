from django_filters import rest_framework as filters
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Country, Subdivision, Address, Language
from .serializers import CountrySerializer, SubdivisionSerializer, AddressSerializer, LanguageSerializer


class CountryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    permission_classes = [IsAuthenticated]


class SubdivisionFilter(filters.FilterSet):
    country = filters.CharFilter(field_name="country__country_code", lookup_expr="iexact")

    class Meta:
        model = Subdivision
        fields = ["country"]


class SubdivisionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Subdivision.objects.all()
    serializer_class = SubdivisionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = SubdivisionFilter

    def get_queryset(self):
        qs = Subdivision.objects.all().select_related("country")
        return qs


class LanguageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Language.objects.all()
    serializer_class = LanguageSerializer
    permission_classes = [IsAuthenticated]


class AddressViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = AddressSerializer
    queryset = Address.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        pass
