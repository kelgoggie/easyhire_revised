from django.urls import path
from . import views
from apps.jobseekers import views as jobseeker_views

app_name = 'jobs'

urlpatterns = [
    path('jobs/', views.PublicJobListView.as_view(), name='job_list'),
    path('jobs/<hashid:pk>/', views.PublicJobDetailView.as_view(), name='job_detail'),
    path('jobs/<hashid:job_id>/save/', jobseeker_views.job_like, name='job_like'),
    path('jobs/<hashid:job_id>/hide/', jobseeker_views.job_hide, name='job_hide'),
    path('jobs/<hashid:job_id>/apply/', jobseeker_views.job_apply, name='job_apply'),
    path('jobs/view/<hashid:pk>/', views.JobseekerJobDetailView.as_view(), name='jobseeker_job_detail'),
]