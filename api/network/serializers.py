from datetime import date

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
    # The EOIR roster gives a rep no contact details or location of their own —
    # you reach them through their recognized organization. Surface that
    # organization's name, phone and place so the directory can list and
    # contact them without an extra round-trip per card.
    organization_name = serializers.SerializerMethodField()
    organization_phone = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    state = serializers.SerializerMethodField()
    # Days until accreditation lapses: negative once expired, null when the
    # roster listed no date. Lets the UI flag soon-to-expire accreditations.
    days_left = serializers.SerializerMethodField()

    class Meta:
        model = Representative
        fields = (
            "id",
            "name",
            "provider_type",
            "credential",
            "organization",
            "organization_name",
            "organization_phone",
            "email",
            "phone",
            "website",
            "address",
            "city",
            "state",
            "dhs_only",
            "accreditation_expiration",
            "days_left",
            "is_active",
            "source_url",
            "last_verified",
        )

    def get_organization_name(self, obj):
        return obj.organization.name if obj.organization_id else None

    def get_organization_phone(self, obj):
        if obj.organization_id and obj.organization.phones:
            return obj.organization.phones[0]
        return None

    @staticmethod
    def _org_address(obj):
        return obj.organization.address if obj.organization_id else None

    def get_city(self, obj):
        address = self._org_address(obj)
        return address.city if address else None

    def get_state(self, obj):
        address = self._org_address(obj)
        if address and address.subdivision_id:
            return address.subdivision.name
        return None

    def get_days_left(self, obj):
        if not obj.accreditation_expiration:
            return None
        return (obj.accreditation_expiration - date.today()).days


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
