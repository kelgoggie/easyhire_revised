from django.urls import path
from . import views

app_name = 'jobseekers'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('resume/', views.resume, name='resume'),
    path('jobs/for-you/', views.recommended_jobs, name='recommended_jobs'),
<<<<<<< HEAD
    path('applications/', views.applications, name='applications'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/picture/upload/', views.profile_picture_upload, name='profile_picture_upload'),
    path('profile/picture/remove/', views.profile_picture_remove, name='profile_picture_remove'),
    path('resume/parse-pdf/', views.parse_resume_pdf, name='parse_resume_pdf'),
=======
>>>>>>> 4332066b7c26abeb5f6e206f1bbc8ba1d999b2e2
    path('jobs/<int:job_id>/like/', views.job_like, name='job_like'),
    path('jobs/<int:job_id>/hide/', views.job_hide, name='job_hide'),
    path('api/autocomplete/skills/', views.autocomplete_skills, name='autocomplete_skills'),
    path('api/autocomplete/positions/', views.autocomplete_positions, name='autocomplete_positions'),
    path('api/autocomplete/degrees/', views.autocomplete_degrees, name='autocomplete_degrees'),
    path('api/autocomplete/certifications/', views.autocomplete_certifications, name='autocomplete_certifications'),
]