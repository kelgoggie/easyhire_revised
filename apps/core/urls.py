from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('api/provinces/', views.provinces_api, name='provinces'),
    path('api/cities/<str:province_code>/', views.cities_api, name='cities'),
    path('api/barangays/<str:city_code>/', views.barangays_api, name='barangays'),
    
]