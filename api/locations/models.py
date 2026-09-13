from django.db import models
from django_countries.fields import CountryField


class Country(models.Model):
    country_code = CountryField(unique=True, db_index=True)
    name = models.CharField(max_length=128)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Subdivision(models.Model):
    code = models.CharField(max_length=10, db_index=True, unique=True)  # e.g. US-CA
    name = models.CharField(max_length=128)
    type = models.CharField(max_length=64, blank=True)
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="subdivisions")

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["country"])]

    def __str__(self):
        return self.name


class Address(models.Model):
    address_name = models.CharField(max_length=255, blank=True, default="Primary Address")
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=128)
    subdivision = models.ForeignKey(Subdivision, null=True, on_delete=models.SET_NULL, related_name="subdivision")
    postal_code = models.CharField(max_length=32, blank=True)
    formatted = models.CharField(max_length=512, blank=True)


class Language(models.Model):
    code = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=128)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["code"])]

    def __str__(self):
        return self.name
