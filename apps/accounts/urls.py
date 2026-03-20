from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Jobseeker auth
    path('login/', views.JobseekerLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.RegisterStep1JobseekerView.as_view(), name='register_step1'),
    path('register/info/', views.RegisterStep2JobseekerView.as_view(), name='register_step2'),

    # Employer auth
    path('employers/login/', views.EmployerLoginView.as_view(), name='employer_login'),
    path('employers/register/', views.EmployerRegisterStep1View.as_view(), name='employer_register_step1'),
    path('employers/register/info/', views.EmployerRegisterStep2View.as_view(), name='employer_register_step2'),
]