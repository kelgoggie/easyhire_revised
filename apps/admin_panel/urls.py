from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('admin-panel/login/', views.admin_login, name='login'),
    path('admin-panel/logout/', views.admin_logout, name='logout'),
    path('admin-panel/', views.dashboard, name='dashboard'),
    path('admin-panel/employers/', views.employer_list, name='employer_list'),
    path('admin-panel/employers/<int:company_id>/', views.employer_detail, name='employer_detail'),
    path('admin-panel/employers/<int:company_id>/verify/', views.set_verification, name='set_verification'),

    # Phase 2 — Jobseekers
    path('admin-panel/jobseekers/',                                       views.jobseeker_list,                  name='jobseeker_list'),
    path('admin-panel/jobseekers/<int:pk>/',                              views.jobseeker_detail,                name='jobseeker_detail'),
    path('admin-panel/jobseekers/<int:pk>/settings/',                     views.jobseeker_settings,              name='jobseeker_settings'),
    path('admin-panel/jobseekers/<int:pk>/applications/<int:app_id>/',    views.jobseeker_application_detail,    name='jobseeker_application_detail'),
]