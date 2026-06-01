from django.http import JsonResponse
from .models import Province, CityMunicipality, Barangay


def provinces_api(request):
    provinces = Province.objects.values('code', 'name')
    return JsonResponse(list(provinces), safe=False)


def cities_api(request, province_code):
    cities = CityMunicipality.objects.filter(
        province__code=province_code
    ).values('code', 'name')
    return JsonResponse(list(cities), safe=False)


def barangays_api(request, city_code):
    barangays = Barangay.objects.filter(
        city__code=city_code
    ).values('code', 'name')
    return JsonResponse(list(barangays), safe=False)