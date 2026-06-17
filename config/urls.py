from django.contrib import admin
from django.urls import path, include, register_converter
from django.views.generic import TemplateView, RedirectView
from django.conf import settings
from django.conf.urls.static import static

from apps.core.hashids import HashidConverter

# Register once so URL patterns app-wide can use ``<hashid:pk>``.
register_converter(HashidConverter, 'hashid')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    # Root takes everyone straight to the jobseeker sign-in. Already-logged-in
    # users get bounced to their dashboard by JobseekerLoginView.
    path('', RedirectView.as_view(url='/login/', permanent=False), name='landing'),
    path('about/',   TemplateView.as_view(template_name='public/about.html'),   name='about'),
    path('terms/',   TemplateView.as_view(template_name='public/terms.html'),   name='terms'),
    path('privacy/', TemplateView.as_view(template_name='public/privacy.html'), name='privacy'),
    path('', include('apps.jobs.urls')),
    path('', include('apps.accounts.urls')),
    path('', include('apps.core.urls')),
    path('', include('apps.jobseekers.urls')),
    path('', include('apps.analytics.urls')),
    path('', include('apps.employers.urls')),
    path('', include('apps.admin_panel.urls')),
    path('', include('apps.notifications.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
