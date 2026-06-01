from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
<<<<<<< HEAD
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
=======

urlpatterns = [
    path('admin/', admin.site.urls),
>>>>>>> 4332066b7c26abeb5f6e206f1bbc8ba1d999b2e2
    path('', TemplateView.as_view(template_name='public/landing_jobseeker.html'), name='landing'),
    path('', include('apps.jobs.urls')),
    path('', include('apps.accounts.urls')),
    path('', include('apps.core.urls')),
    path('', include('apps.jobseekers.urls')),
    path('', include('apps.analytics.urls')),
    path('', include('apps.employers.urls')),
    path('', include('apps.admin_panel.urls')),
    path('', include('apps.notifications.urls')),
<<<<<<< HEAD
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
=======
]
>>>>>>> 4332066b7c26abeb5f6e206f1bbc8ba1d999b2e2
