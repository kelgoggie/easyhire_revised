from django.urls import path
from . import views

app_name = 'jobs'

urlpatterns = [
    path('jobs/', views.PublicJobListView.as_view(), name='job_list'),
    path('jobs/<int:pk>/', views.PublicJobDetailView.as_view(), name='job_detail'),
]