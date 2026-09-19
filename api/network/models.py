from django.contrib.postgres.fields import ArrayField
from django.db import models


class OrganizationType(models.TextChoices):
    """Mirrors data/schema/resource.schema.json ``org_type`` (see vocabularies.md)."""

    SELF_OWNED = "self-owned", "Self Owned"
    PUBLIC_COMPANY = "public-company", "Public Company"
    PRIVATE_COMPANY = "private-company", "Private Company"
    PARTNERSHIP = "partnership", "Partnership"
    EDUCATIONAL = "educational", "Educational"
    REFERRAL_SERVICE = "referral-service", "Referral Service"
    COMMUNITY_ORGANIZATION = "community-organization", "Community Organization"
    NONPROFIT = "non-profit", "Non-profit"


class FeeModel(models.TextChoices):
    FREE = "free", "Free"
    SLIDING_SCALE = "sliding-scale", "Sliding scale"
    LOW_COST = "low-cost", "Low cost"
    PAID = "paid", "Paid"
    UNKNOWN = "unknown", "Unknown"


class ProviderType(models.TextChoices):
    ATTORNEY = "attorney", "Attorney"
    DOJ_ACCREDITED_REP = "doj-accredited-rep", "DOJ Accredited Representative"


class Organization(models.Model):
    """A place a person can get immigration help.

    The columns mirror ``data/schema/resource.schema.json`` one-to-one so curated
    resource YAML loads straight in (see the ``load_resources`` command). Contact
    details that used to fan out into side-tables now live inline as Postgres
    arrays.
    """

    name = models.CharField(max_length=500)
    # slug is the schema's ``org_id`` — stable and unique within the directory.
    slug = models.SlugField(unique=True)
    organization_type = models.CharField(max_length=32, choices=OrganizationType.choices)
    description = models.TextField(blank=True)

    pro_bono = models.BooleanField(default=False)
    fee_model = models.CharField(max_length=16, choices=FeeModel.choices, blank=True)
    # e.g. "DOJ-recognized" — a strong trust signal.
    accreditation = models.CharField(max_length=255, blank=True)

    # Controlled vocab (data/schema/vocabularies.md); ISO 639-1 for languages.
    services = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    languages = ArrayField(models.CharField(max_length=8), default=list, blank=True)

    address = models.ForeignKey(
        "locations.Address", null=True, blank=True, on_delete=models.SET_NULL
    )
    websites = ArrayField(models.URLField(), default=list, blank=True)
    emails = ArrayField(models.EmailField(), default=list, blank=True)
    phones = ArrayField(models.CharField(max_length=64), default=list, blank=True)

    country = models.CharField(max_length=2, default="US")  # ISO 3166-1 alpha-2

    # Trust signals: where the listing was sourced/verified, and when.
    source_url = models.URLField(blank=True)
    last_verified = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Representative(models.Model):
    """An individual provider — a licensed attorney or a DOJ-accredited rep.

    Replaces the old bar-licensure-only ``Attorney`` so the directory can list
    DOJ-accredited representatives too. Read-only and empty for now; populating
    it from the EOIR roster is a follow-up.
    """

    name = models.CharField(max_length=255)
    provider_type = models.CharField(max_length=32, choices=ProviderType.choices)
    # Bar number (attorneys) or accreditation id (DOJ-accredited reps).
    credential = models.CharField(max_length=255, blank=True)

    organization = models.ForeignKey(
        "network.Organization",
        null=True,
        blank=True,
        related_name="representatives",
        on_delete=models.SET_NULL,
    )

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=64, blank=True)
    website = models.URLField(blank=True)
    address = models.ForeignKey(
        "locations.Address", null=True, blank=True, on_delete=models.SET_NULL
    )

    # DOJ-accredited reps can be limited to DHS (USCIS) practice — not authorized
    # to appear before the immigration courts or the BIA. This flags that scope.
    dhs_only = models.BooleanField(default=False)
    accreditation_expiration = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=False)
    source_url = models.URLField(blank=True)
    last_verified = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
