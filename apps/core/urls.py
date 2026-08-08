from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('api/provinces/', views.provinces_api, name='provinces'),
    path('api/cities/<str:province_code>/', views.cities_api, name='cities'),
    path('api/barangays/<str:city_code>/', views.barangays_api, name='barangays'),
    path('help/', views.help_view, name='help'),
    path('inbox/', views.inbox, name='inbox'),
    path('inbox/dismiss/', views.inbox_dismiss, name='inbox_dismiss'),
    path('inbox/pin/', views.inbox_pin, name='inbox_pin'),
    path('inbox/bulk-dismiss/', views.inbox_bulk_dismiss, name='inbox_bulk_dismiss'),
]