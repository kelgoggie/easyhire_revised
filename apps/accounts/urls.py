from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'accounts'

urlpatterns = [
    # Jobseeker auth
    path('login/', views.JobseekerLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.RegisterStep1JobseekerView.as_view(), name='register_step1'),
    path('register/info/', views.RegisterStep2JobseekerView.as_view(), name='register_step2'),

    # One-click resend for the "Verify your email" banner. JSON endpoint,
    # session-rate-limited to one send per 30 seconds.
    path('accounts/resend-verification/', views.resend_verification_email,
         name='resend_verification'),

    # PESO-mediated password recovery. Static info page — password resets
    # go through easyhire.admin@gmail.com because SMTP isn't configured
    # against a verified sender domain. See admin_panel/jobseeker_settings
    # for the "Generate Temporary Password" flow admins use to service
    # incoming requests.
    path('password-recovery/', TemplateView.as_view(
        template_name='public/password_recovery.html'
    ), name='password_recovery'),

    # Employer auth
    path('employers/login/', views.EmployerLoginView.as_view(), name='employer_login'),
    path('employers/register/', views.EmployerRegisterStep1View.as_view(), name='employer_register_step1'),
    path('employers/register/info/', views.EmployerRegisterStep2View.as_view(), name='employer_register_step2'),
]