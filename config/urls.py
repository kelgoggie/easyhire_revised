from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='public/landing_jobseeker.html'), name='landing'),
    path('', include('apps.jobs.urls')),
    path('', include('apps.accounts.urls')),
    path('', include('apps.core.urls')),
    path('', include('apps.jobseekers.urls')),
    path('', include('apps.employers.urls')),
    path('', include('apps.analytics.urls')),
    path('', include('apps.admin_panel.urls')),
]