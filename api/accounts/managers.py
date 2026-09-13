from django.apps import apps as django_apps
from django.contrib.auth.models import UserManager as BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        Profile = django_apps.get_model("accounts", "Profile")
        user = super().create_user(username, email=email, password=password, **extra_fields)
        # Ensure a Profile is created for every new user
        Profile.objects.get_or_create(user=user)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        Profile = django_apps.get_model("accounts", "Profile")
        user = super().create_superuser(username, email=email, password=password, **extra_fields)
        # Ensure a Profile is created for superusers as well
        Profile.objects.get_or_create(user=user)
        return user
