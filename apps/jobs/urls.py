from django.urls import path
from . import views
from apps.jobseekers import views as jobseeker_views

app_name = 'jobs'

urlpatterns = [
    path('jobs/', views.PublicJobListView.as_view(), name='job_list'),
    path('jobs/<int:pk>/', views.PublicJobDetailView.as_view(), name='job_detail'),
    path('jobs/<int:job_id>/save/', jobseeker_views.job_like, name='job_like'),
    path('jobs/<int:job_id>/hide/', jobseeker_views.job_hide, name='job_hide'),
    path('jobs/view/<int:pk>/', views.JobseekerJobDetailView.as_view(), name='jobseeker_job_detail'),
]