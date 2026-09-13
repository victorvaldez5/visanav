import pycountry
from django.core.management.base import BaseCommand

from locations.models import Country, Subdivision


class Command(BaseCommand):
    help = "Seed countries and subdivisions from pycountry"

    def handle(self, *args, **options):
        # Countries
        for c in pycountry.countries:
            Country.objects.update_or_create(country_code=c.alpha_2, defaults={"name": c.name})

        # Subdivisions
        # pycountry.subdivisions has fields: code (e.g., US-CA), name, type, country_code
        Subdivision.objects.all().delete()  # or upsert if you need stable IDs
        to_create = []
        for s in pycountry.subdivisions:
            try:
                country = Country.objects.get(country_code=s.country_code)
            except Country.DoesNotExist:
                continue
            to_create.append(Subdivision(
                code=s.code,
                name=s.name,
                type=getattr(s, "type", ""),
                country=country,
            ))
        Subdivision.objects.bulk_create(to_create, batch_size=1000)
        self.stdout.write(self.style.SUCCESS("Seeded countries and subdivisions"))
