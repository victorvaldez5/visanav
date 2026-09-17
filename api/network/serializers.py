from rest_framework import serializers

from locations.serializers import AddressSerializer
from network.models import Organization, Representative


class OrganizationSerializer(serializers.ModelSerializer):
    # Contact details are inline arrays on the row; only the address is nested.
    address = AddressSerializer(read_only=True)

    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "slug",
            "organization_type",
            "description",
            "pro_bono",
            "fee_model",
            "accreditation",
            "services",
            "languages",
            "address",
            "websites",
            "emails",
            "phones",
            "country",
            "source_url",
            "last_verified",
            "is_active",
        )


class RepresentativeSerializer(serializers.ModelSerializer):
    address = AddressSerializer(read_only=True)

    class Meta:
        model = Representative
        fields = (
            "id",
            "name",
            "provider_type",
            "credential",
            "organization",
            "email",
            "phone",
            "website",
            "address",
            "is_active",
            "source_url",
            "last_verified",
        )
