from rest_framework import serializers

from core.utils import assert_turnstile
from locations.serializers import AddressSerializer
from network.models import Organization, Representative, OrganizationSubmission


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
            "dhs_only",
            "accreditation_expiration",
            "is_active",
            "source_url",
            "last_verified",
        )


class OrganizationSubmissionSerializer(serializers.ModelSerializer):
    # Honeypot: a real user's browser leaves this empty; bots fill every field.
    # Named to look enticing to a scraper. write_only so it never round-trips.
    hp_website = serializers.CharField(required=False, allow_blank=True, write_only=True)
    # Cloudflare Turnstile token, verified server-side in validate().
    turnstile_token = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = OrganizationSubmission
        # status/reviewer_notes are staff-only and deliberately NOT writable here.
        fields = (
            "id",
            "organization_name",
            "contact_name",
            "contact_email",
            "contact_phone",
            "website",
            "city",
            "state",
            "offers_pro_bono",
            "intent",
            "message",
            "hp_website",
            "turnstile_token",
        )
        read_only_fields = ("id",)

    def validate_hp_website(self, value):
        if value:
            # A filled honeypot means a bot; reject without revealing why.
            raise serializers.ValidationError("Invalid submission.")
        return value

    def validate(self, attrs):
        # A client can spoof the widget, so this server check is the real gate
        # (no-op unless TURNSTILE_SECRET_KEY is set).
        assert_turnstile(attrs.get("turnstile_token", ""), self.context.get("request"))
        return attrs

    def create(self, validated_data):
        validated_data.pop("hp_website", None)
        validated_data.pop("turnstile_token", None)
        return super().create(validated_data)
