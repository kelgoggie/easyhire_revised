from django.urls import path
from . import views

app_name = 'jobseekers'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('resume/', views.resume, name='resume'),
]