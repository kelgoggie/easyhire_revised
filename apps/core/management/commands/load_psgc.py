import json
import os
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.core.models import Province, CityMunicipality, Barangay

<<<<<<< HEAD
ILOILO_CODE = '063000000'


class Command(BaseCommand):
    help = 'Loads Iloilo PSGC data (provinces, cities, barangays) from local JSON files'
=======

class Command(BaseCommand):
    help = 'Loads Philippine location data from local JSON files'
>>>>>>> 4332066b7c26abeb5f6e206f1bbc8ba1d999b2e2

    def handle(self, *args, **kwargs):
        data_dir = os.path.join(settings.BASE_DIR, 'static', 'data')

<<<<<<< HEAD
        # ── Provinces (load only Iloilo) ──────────────────────────
        self.stdout.write('Loading Iloilo province...')
        with open(os.path.join(data_dir, 'provinces.json'), encoding='utf-8') as f:
            provinces_data = json.load(f)

        iloilo_data = next((p for p in provinces_data if p['code'] == ILOILO_CODE), None)
        if not iloilo_data:
            self.stderr.write(self.style.ERROR(f'Iloilo province (code {ILOILO_CODE}) not found in provinces.json'))
            return

        province, _ = Province.objects.get_or_create(
            code=iloilo_data['code'],
            defaults={'name': iloilo_data['name']},
        )
        self.stdout.write(self.style.SUCCESS(f'Province ready: {province.name}'))

        # ── Cities/Municipalities (Iloilo only) ───────────────────
        self.stdout.write('Loading Iloilo cities/municipalities...')
        with open(os.path.join(data_dir, 'cities.json'), encoding='utf-8') as f:
            cities_data = json.load(f)

        iloilo_cities = [c for c in cities_data if c.get('provinceCode') == ILOILO_CODE]

        existing_city_codes = set(CityMunicipality.objects.filter(
            province=province
        ).values_list('code', flat=True))

        new_cities = [
            CityMunicipality(code=c['code'], name=c['name'], province=province)
            for c in iloilo_cities if c['code'] not in existing_city_codes
        ]
        CityMunicipality.objects.bulk_create(new_cities, ignore_conflicts=True)

        city_map = {
            c.code: c
            for c in CityMunicipality.objects.filter(province=province)
        }
        self.stdout.write(self.style.SUCCESS(
            f'Cities/municipalities ready: {len(city_map)} total '
            f'({len(new_cities)} newly inserted)'
        ))

        # ── Barangays (Iloilo only) ───────────────────────────────
        self.stdout.write('Loading Iloilo barangays...')
        with open(os.path.join(data_dir, 'barangays.json'), encoding='utf-8') as f:
            barangays_data = json.load(f)

        iloilo_city_codes = set(city_map.keys())
        iloilo_barangays = [
            b for b in barangays_data
            if (b.get('municipalityCode') or b.get('cityCode')) in iloilo_city_codes
        ]

        existing_bar_codes = set(
            Barangay.objects.filter(city__in=city_map.values())
                            .values_list('code', flat=True)
        )

        new_barangays = []
        for b in iloilo_barangays:
            city_code = b.get('municipalityCode') or b.get('cityCode')
            city = city_map.get(city_code)
            if city and b['code'] not in existing_bar_codes:
                new_barangays.append(Barangay(code=b['code'], name=b['name'], city=city))

        # Bulk insert in chunks to avoid oversized queries
        chunk = 500
        for i in range(0, len(new_barangays), chunk):
            Barangay.objects.bulk_create(new_barangays[i:i+chunk], ignore_conflicts=True)

        total_barangays = Barangay.objects.filter(city__in=city_map.values()).count()
        self.stdout.write(self.style.SUCCESS(
            f'Barangays ready: {total_barangays} total '
            f'({len(new_barangays)} newly inserted)'
        ))
        self.stdout.write(self.style.SUCCESS('PSGC data loaded successfully!'))
=======
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
>>>>>>> 4332066b7c26abeb5f6e206f1bbc8ba1d999b2e2
