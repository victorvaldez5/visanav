from rest_framework import serializers

from .models import Country, Subdivision, Address, Language


class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ("id", "country_code", "name")


class SubdivisionSerializer(serializers.ModelSerializer):
    country = CountrySerializer()

    class Meta:
        model = Subdivision
        fields = ("id", "code", "name", "type", "country")


class AddressSerializer(serializers.ModelSerializer):
    subdivision = SubdivisionSerializer()

    class Meta:
        model = Address
        fields = ("line1", "line2", "city", "postal_code", "subdivision")


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Language
        fields = ("id", "code", "name")
