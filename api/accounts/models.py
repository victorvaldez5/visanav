from django.contrib.auth.models import AbstractUser
from django.db import models
from phonenumber_field.modelfields import PhoneNumberField

from accounts.managers import UserManager


# Create your models here.
class User(AbstractUser):
    is_verified = models.BooleanField(default=False)
    middle_name = models.CharField(max_length=255, null=True, blank=True)
    phone_number = PhoneNumberField(blank=True, null=True)

    objects = UserManager()

    def __str__(self):
        return self.username


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")

    # Locale
    preferred_language = models.ForeignKey('locations.Language', to_field="code", null=True, blank=True,
                                           on_delete=models.SET_NULL)
    country = models.ForeignKey('locations.Country', to_field="country_code", null=True, blank=True,
                                on_delete=models.SET_NULL)  # ISO 3166-1 alpha-2 (e.g., "US", "DE")
    subdivision = models.ForeignKey('locations.Subdivision', to_field="code", null=True, blank=True,
                                    on_delete=models.SET_NULL)  # ISO 3166-1 alpha-2 (e.g., "US", "DE")
    postal_code = models.CharField(max_length=32, blank=True)

    # Notifications
    notify_system = models.BooleanField(default=True)
    notify_marketing = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} Profile"
