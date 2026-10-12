from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils.translation import gettext as _
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from rest_framework.serializers import CharField, ModelSerializer
from rest_framework_simplejwt.serializers import AuthUser, TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import Token

from accounts.models import Profile
from core.utils import assert_turnstile
from locations.models import Subdivision, Country, Language

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user: AuthUser) -> Token:
        token = super().get_token(user)

        token["username"] = user.username
        token["email"] = user.email
        return token

    def validate(self, attrs):
        # Bot check before we hit the (slow, brute-forceable) password path.
        assert_turnstile(self.initial_data.get("turnstile_token", ""), self.context.get("request"))
        return super().validate(attrs)


class RegisterSerializer(ModelSerializer):
    password = CharField(write_only=True, trim_whitespace=False)
    password2 = CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ("email", "password", "password2")

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_("Email already exists."))
        return value

    def validate_password(self, value):
        if value != self.initial_data.get("password2"):
            raise serializers.ValidationError(_("Passwords do not match."))
        validate_password(value)
        return value

    def validate(self, attrs):
        assert_turnstile(self.initial_data.get("turnstile_token", ""), self.context.get("request"))
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["email"], email=validated_data["email"], password=validated_data["password"]
        )


class UserSerializer(ModelSerializer):
    phone_number = PhoneNumberField(region="US", required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("email", "first_name", "middle_name", "last_name", "phone_number")


class ProfileSerializer(ModelSerializer):
    country = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all())
    subdivision = serializers.PrimaryKeyRelatedField(queryset=Subdivision.objects.all())
    # Read and written as the locale code ("es"), limited to the i18n allowlist
    # (settings.LANGUAGES), so a profile can only hold a language the app ships.
    preferred_language = serializers.SlugRelatedField(
        slug_field="code",
        queryset=Language.objects.filter(code__in=[code for code, _name in settings.LANGUAGES]),
        allow_null=True,
        required=False,
    )

    class Meta:
        model = Profile
        fields = ("country", "subdivision", "preferred_language", "postal_code", "notify_marketing", "notify_system", "retain_history")
