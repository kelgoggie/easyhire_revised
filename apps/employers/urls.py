from django.urls import path
from . import views

app_name = 'employers'

urlpatterns = [
    path('employers/', views.landing, name='landing'),
    path('employers/dashboard/', views.dashboard, name='dashboard'),
    path('employers/pending/', views.pending, name='pending'),
    path('employers/upload-document/', views.upload_document, name='upload_document'),
    path('employers/submit-verification/', views.submit_verification, name='submit_verification'),
    path('employers/jobs/', views.job_list, name='job_list'),
    path('employers/jobs/create/', views.job_create, name='job_create'),
    path('employers/jobs/<hashid:job_id>/', views.job_detail, name='job_detail'),
    path('employers/jobs/<hashid:job_id>/edit/', views.job_edit, name='job_edit'),
    path('employers/jobs/<hashid:job_id>/delete/',  views.job_delete,  name='job_delete'),
    path('employers/jobs/<hashid:job_id>/restore/', views.job_restore, name='job_restore'),
    path('employers/jobs/<hashid:job_id>/close/',   views.job_close,   name='job_close'),
    path('employers/jobs/<hashid:job_id>/candidates/', views.candidates, name='candidates'),
    path('employers/jobs/<hashid:job_id>/invite/<hashid:jobseeker_id>/', views.invite_to_apply, name='invite_to_apply'),
    path('employers/candidates/<hashid:jobseeker_id>/like/', views.candidate_like, name='candidate_like'),
    path('employers/candidates/<hashid:jobseeker_id>/contact/', views.candidate_contact, name='candidate_contact'),
    path('employers/profile/', views.company_profile, name='company_profile'),
    path('employers/all_candidates/', views.all_candidates, name='all_candidates'),
    path('employers/candidates/<hashid:jobseeker_id>/', views.candidate_detail, name='candidate_detail'),
    path('employers/applications/<hashid:app_id>/status/', views.application_update_status, name='application_update_status'),
    path('employers/settings/', views.employer_settings, name='employer_settings'),
]