from django.urls import path
from . import views

urlpatterns = [
    path('api/notifications/', views.notifications_api, name='notifications_api'),
    path('api/notifications/<int:notif_id>/read/', views.mark_read, name='mark_read'),
    path('api/notifications/read-all/', views.mark_all_read, name='mark_all_read'),
]