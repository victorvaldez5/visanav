from datetime import date, timedelta

import django_filters
from django.db.models import Q
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
    # Cost chips OR together across the pro-bono flag and one or more fee
    # models, so picking "Pro bono" + "Free" widens the list instead of
    # emptying it (a single fee_model= would only match one exact value).
    cost = django_filters.MultipleChoiceFilter(
        method="filter_cost",
        choices=[
            ("pro_bono", "Pro bono"),
            ("free", "Free"),
            ("low-cost", "Low cost"),
            ("sliding-scale", "Sliding scale"),
        ],
    )

    class Meta:
        model = Organization
        fields = ["organization_type", "pro_bono", "fee_model"]

    def filter_service(self, queryset, name, value):
        return queryset.filter(services__contains=[value])

    def filter_language(self, queryset, name, value):
        return queryset.filter(languages__contains=[value])

    def filter_cost(self, queryset, name, values):
        if not values:
            return queryset
        fee_models = [v for v in values if v != "pro_bono"]
        query = Q()
        if "pro_bono" in values:
            query |= Q(pro_bono=True)
        if fee_models:
            query |= Q(fee_model__in=fee_models)
        return queryset.filter(query)


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrganizationSerializer
    permission_classes = (AllowAny,)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "slug"]
    filterset_class = OrganizationFilter
    ordering_fields = ["name", "last_verified", "address__subdivision__name"]
    ordering = ["name"]

    def get_queryset(self):
        # Contact details are on the row now; only the address is a join.
        return Organization.objects.filter(is_active=True).select_related(
            "address", "address__subdivision"
        )


class RepresentativeFilter(FilterSet):
    # A rep has no location of their own; filter by their organization's state
    # (subdivision name, e.g. "Arizona") to match the OrganizationFilter.region.
    region = django_filters.CharFilter(
        field_name="organization__address__subdivision__name", lookup_expr="iexact"
    )
    # Reps whose accreditation lapses within N days (and hasn't already);
    # backs the "expiring soon" chip. Excludes undated rows (unknown != soon).
    expires_within = django_filters.NumberFilter(method="filter_expires_within")

    class Meta:
        model = Representative
        fields = ["provider_type", "organization", "dhs_only"]

    def filter_expires_within(self, queryset, name, value):
        try:
            days = int(value)
        except (TypeError, ValueError):
            return queryset
        today = date.today()
        return queryset.filter(
            accreditation_expiration__gte=today,
            accreditation_expiration__lte=today + timedelta(days=days),
        )


class RepresentativeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = RepresentativeSerializer
    permission_classes = (AllowAny,)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "organization__name"]
    filterset_class = RepresentativeFilter
    ordering_fields = ["name", "accreditation_expiration", "organization__name"]
    # Soonest-to-expire first by default (nulls sort last in Postgres).
    ordering = ["accreditation_expiration", "name"]

    def get_queryset(self):
        # A lapsed accreditation can't represent anyone, so keep expired reps
        # out of the public directory — but keep undated rows (roster gave no
        # expiration) visible rather than guessing they're expired.
        return (
            Representative.objects.filter(is_active=True)
            .exclude(accreditation_expiration__lt=date.today())
            .select_related(
                "organization",
                "organization__address",
                "organization__address__subdivision",
                "address",
                "address__subdivision",
            )
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
