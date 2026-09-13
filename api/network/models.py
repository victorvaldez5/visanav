from django.db import models


class Attorney(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=255)
    address = models.ForeignKey("locations.Address", on_delete=models.CASCADE)

    bar_number = models.CharField(max_length=255)
    bar_number_verified = models.BooleanField(default=False)
    bar_start = models.DateField()
    bar_end = models.DateField()

    website = models.URLField()
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Organization(models.Model):
    class OrganizationType(models.TextChoices):
        SELF_OWNED = "self-owned", "Self Owned"
        PUBLIC_COMPANY = "public-company", "Public Company"
        PRIVATE_COMPANY = "private-company", "Private Company"
        PARTNERSHIP = "partnership", "Partnership"
        EDUCATIONAL = "educational", "Educational"
        REFERRAL_SERVICE = "referral-service", "Referral service"
        COMMUNITY_ORGANIZATION = "community-organization", "Community Organization"
        NONPROFIT = "non-profit", "Non-profit"

    name = models.CharField(max_length=500)
    slug = models.SlugField(unique=True)
    organization_type = models.CharField(max_length=255)
    notes = models.TextField(blank=True)
    has_pro_bono = models.BooleanField(default=False)

    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class OrganizationAddress(models.Model):
    address = models.ForeignKey("locations.Address", on_delete=models.CASCADE)
    organization = models.ForeignKey("network.Organization", related_name="addresses", on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)

    class Meta:
        unique_together = ("address", "organization")


class OrganizationPhoneNumber(models.Model):
    phone_number = models.CharField(max_length=255)
    organization = models.ForeignKey("network.Organization", related_name="phone_numbers", on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)

    class Meta:
        unique_together = ("phone_number", "organization")


class OrganizationEmail(models.Model):
    email = models.EmailField()
    organization = models.ForeignKey("network.Organization", related_name="emails", on_delete=models.CASCADE)
    is_primary = models.BooleanField(default=False)

    class Meta:
        unique_together = ("email", "organization")

    def __str__(self):
        return self.email


class OrganizationWebsites(models.Model):
    website = models.URLField()
    organization = models.ForeignKey("network.Organization", related_name="websites", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("website", "organization")

    def __str__(self):
        return self.website


class OrganizationLanguage(models.Model):
    language = models.ForeignKey("locations.Language", on_delete=models.CASCADE)
    organization = models.ForeignKey("network.Organization", related_name="languages", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("language", "organization")


class OrganizationSocialLink(models.Model):
    class SocialLinkType(models.TextChoices):
        FACEBOOK = "facebook", "Facebook"
        TWITTER = "twitter", "Twitter"
        INSTAGRAM = "instagram", "Instagram"
        LINKEDIN = "linkedin", "LinkedIn"
        X = "x", "X",
        YOUTUBE = "youtube", "YouTube"
        TIKTOK = "tiktok", "TikTok"
        OTHER = "other", "Other"

    platform = models.CharField(max_length=255, choices=SocialLinkType.choices)
    link = models.URLField()
    organization = models.ForeignKey("network.Organization", related_name="social_links", on_delete=models.CASCADE)


class OrganizationMember(models.Model):
    attorney = models.ForeignKey("network.Attorney", on_delete=models.CASCADE)
    organization = models.ForeignKey("network.Organization", related_name="attorneys", on_delete=models.CASCADE)

    membership_start_date = models.DateField()
    membership_end_date = models.DateField()

    class Meta:
        unique_together = ("attorney", "organization")

    def __str__(self):
        return f"{self.attorney} - {self.organization}"
