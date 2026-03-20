import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.core.models import Province, CityMunicipality, Barangay


class Command(BaseCommand):
    help = 'Loads Philippine location data from local JSON files'

    def handle(self, *args, **kwargs):
        data_dir = os.path.join(settings.BASE_DIR, 'static', 'data')

        # --- Load Provinces ---
        self.stdout.write('Loading provinces...')
        with open(os.path.join(data_dir, 'provinces.json'), encoding='utf-8') as f:
            provinces_data = json.load(f)

        province_map = {}
        for item in provinces_data:
            province, _ = Province.objects.get_or_create(
                code=item['code'],
                defaults={'name': item['name']}
            )
            province_map[item['code']] = province

        self.stdout.write(self.style.SUCCESS(f'Loaded {len(province_map)} provinces.'))

        # --- Load Cities/Municipalities ---
        self.stdout.write('Loading cities and municipalities...')
        with open(os.path.join(data_dir, 'cities.json'), encoding='utf-8') as f:
            cities_data = json.load(f)

        city_map = {}
        skipped_cities = 0
        for item in cities_data:
            province_code = item.get('provinceCode')
            province = province_map.get(province_code)
            if not province:
                skipped_cities += 1
                continue
            city, _ = CityMunicipality.objects.get_or_create(
                code=item['code'],
                defaults={'name': item['name'], 'province': province}
            )
            city_map[item['code']] = city

        self.stdout.write(self.style.SUCCESS(
            f'Loaded {len(city_map)} cities/municipalities. Skipped {skipped_cities}.'
        ))

        # --- Load Barangays ---
        self.stdout.write('Loading barangays (this may take a minute)...')
        with open(os.path.join(data_dir, 'barangays.json'), encoding='utf-8') as f:
            barangays_data = json.load(f)

        loaded = 0
        skipped = 0
        for item in barangays_data:
            city_code = item.get('municipalityCode') or item.get('cityCode')
            city = city_map.get(city_code)
            if not city:
                skipped += 1
                continue
            Barangay.objects.get_or_create(
                code=item['code'],
                defaults={'name': item['name'], 'city': city}
            )
            loaded += 1

        self.stdout.write(self.style.SUCCESS(
            f'Loaded {loaded} barangays. Skipped {skipped}.'
        ))
        self.stdout.write(self.style.SUCCESS('PSGC data loaded successfully!'))