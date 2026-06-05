from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Province, CityMunicipality, Barangay


@login_required
def help_view(request):
    if request.user.is_employer:
        return render(request, 'employers/help.html')
    return render(request, 'jobseekers/help.html')


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