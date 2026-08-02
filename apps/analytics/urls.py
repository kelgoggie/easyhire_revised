from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('analytics/', views.analytics, name='analytics'),
    path('analytics/export.csv', views.analytics_csv, name='analytics_csv'),
]