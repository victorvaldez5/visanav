from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from rest_framework.serializers import CharField, ModelSerializer
from rest_framework_simplejwt.serializers import AuthUser, TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import Token

from accounts.models import Profile
from locations.models import Subdivision, Country, Language

User = get_user_model()


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user: AuthUser) -> Token:
        token = super().get_token(user)

        token["username"] = user.username
        token["email"] = user.email
        return token


class RegisterSerializer(ModelSerializer):
    password = CharField(write_only=True, trim_whitespace=False)
    password2 = CharField(write_only=True, trim_whitespace=False)

    class Meta:
        model = User
        fields = ("email", "password", "password2")

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate_password(self, value):
        if value != self.initial_data.get("password2"):
            raise serializers.ValidationError("Passwords do not match.")
        validate_password(value)
        return value

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
    preferred_language = serializers.PrimaryKeyRelatedField(queryset=Language.objects.all())

    class Meta:
        model = Profile
        fields = ("country", "subdivision", "preferred_language", "postal_code", "notify_marketing", "notify_system", "retain_history")
