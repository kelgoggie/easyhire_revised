from django.urls import path
from . import views

app_name = 'employers'

urlpatterns = [
    path('employers/', views.landing, name='landing'),
    path('employers/dashboard/', views.dashboard, name='dashboard'),
    path('employers/pending/', views.pending, name='pending'),
    path('employers/upload-document/', views.upload_document, name='upload_document'),
    path('employers/jobs/', views.job_list, name='job_list'),
    path('employers/jobs/create/', views.job_create, name='job_create'),
    path('employers/jobs/<int:job_id>/', views.job_detail, name='job_detail'),
    path('employers/jobs/<int:job_id>/edit/', views.job_edit, name='job_edit'),
    path('employers/jobs/<int:job_id>/delete/', views.job_delete, name='job_delete'),
    path('employers/jobs/<int:job_id>/candidates/', views.candidates, name='candidates'),
    path('employers/candidates/<int:jobseeker_id>/like/', views.candidate_like, name='candidate_like'),
    path('employers/profile/', views.company_profile, name='company_profile'),
    path('employers/all_candidates/', views.all_candidates, name='all_candidates'),
    path('employers/candidates/<int:jobseeker_id>/', views.candidate_detail, name='candidate_detail'),
    
]