from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    path('admin-panel/login/', views.admin_login, name='login'),
    path('admin-panel/logout/', views.admin_logout, name='logout'),
    path('admin-panel/', views.dashboard, name='dashboard'),
    path('admin-panel/employers/', views.employer_list, name='employer_list'),
    path('admin-panel/employers/<hashid:company_id>/', views.employer_detail, name='employer_detail'),
    path('admin-panel/employers/<hashid:company_id>/verify/', views.set_verification, name='set_verification'),

    # Phase 2 — Jobseekers
    path('admin-panel/jobseekers/',                                       views.jobseeker_list,                  name='jobseeker_list'),
    path('admin-panel/jobseekers/<hashid:pk>/',                              views.jobseeker_detail,                name='jobseeker_detail'),
    path('admin-panel/jobseekers/<hashid:pk>/settings/',                     views.jobseeker_settings,              name='jobseeker_settings'),
    path('admin-panel/jobseekers/<hashid:pk>/applications/<hashid:app_id>/',    views.jobseeker_application_detail,    name='jobseeker_application_detail'),

    # Phase 3 — Companies
    path('admin-panel/companies/',                                        views.company_list,                    name='company_list'),
    path('admin-panel/companies/<hashid:pk>/',                               views.company_detail,                  name='company_detail'),
    path('admin-panel/companies/<hashid:pk>/settings/',                      views.company_settings,                name='company_settings'),
    path('admin-panel/companies/<hashid:pk>/jobs/<hashid:job_id>/',             views.company_job_detail,              name='company_job_detail'),
    path('admin-panel/companies/<hashid:pk>/jobs/<hashid:job_id>/match/<hashid:jobseeker_id>/', views.job_match_detail,    name='job_match_detail'),
    path('admin-panel/companies/<hashid:pk>/jobs/<hashid:job_id>/delete/',      views.company_delete_job,              name='company_delete_job'),

    # User-facing report submission (jobseeker reports company, employer reports jobseeker)
    path('api/report/',                                                   views.report_submit,                   name='report_submit'),

    # Phase 4 — Algorithm settings + Reports admin
    path('admin-panel/settings/',                                         views.algorithm_settings,              name='algorithm_settings'),
    path('admin-panel/reports/',                                          views.report_list,                     name='report_list'),
    path('admin-panel/reports/<hashid:report_id>/review/',                   views.report_review,                   name='report_review'),

    # Phase 5 — Pending Approvals (personal-info change requests)
    path('admin-panel/change-requests/<hashid:request_id>/review/',          views.change_request_review,           name='change_request_review'),

    # Activity log (audit trail of admin actions)
    path('admin-panel/activity/',                                         views.activity_log,                    name='activity_log'),

    # Bulk import (CSV upload for jobseekers / companies)
    path('admin-panel/import/',                                           views.bulk_import,                     name='bulk_import'),

    # Admin edit a jobseeker's resume
    path('admin-panel/jobseekers/<hashid:pk>/edit-resume/',                  views.admin_edit_resume,               name='admin_edit_resume'),

    # Announcements (broadcast to jobseekers / employers / all)
    path('admin-panel/announcements/',                                    views.announcements,                   name='announcements'),
]