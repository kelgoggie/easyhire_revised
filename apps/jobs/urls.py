from django.urls import path
from . import views

app_name = 'jobs'

urlpatterns = [
    path('', views.landing_jobseeker, name='landing'),
]