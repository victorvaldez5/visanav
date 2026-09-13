from rest_framework import serializers

from locations.serializers import AddressSerializer
from network.models import Organization, OrganizationEmail, OrganizationPhoneNumber, OrganizationWebsites, \
    OrganizationAddress


class OrganizationEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationEmail
        fields = ("id", "email", "is_primary",)


class OrganizationPhoneNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationPhoneNumber
        fields = ("id", "phone_number", "is_primary",)


class OrganizationWebsitesSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationWebsites
        fields = ("id", "website",)


class OrganizationAddressSerializer(serializers.ModelSerializer):
    address = AddressSerializer()

    class Meta:
        model = OrganizationAddress
        fields = ("id", "address", "is_primary",)


class OrganizationSerializer(serializers.ModelSerializer):
    emails = OrganizationEmailSerializer(many=True)
    phone_numbers = OrganizationPhoneNumberSerializer(many=True)
    websites = OrganizationWebsitesSerializer(many=True)
    addresses = OrganizationAddressSerializer(many=True)

    class Meta:
        model = Organization
        fields = (
            "id",
            "name",
            "slug",
            "has_pro_bono",
            "organization_type",
            "notes",
            "description",
            "is_active",
            "addresses",
            "emails",
            "phone_numbers",
            "websites",
        )
