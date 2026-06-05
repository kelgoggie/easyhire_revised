from django.shortcuts import render

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Notification


def _relative_time(dt):
    s = int((timezone.now() - dt).total_seconds())
    if s < 60:     return f"{max(s, 1)}s ago"
    if s < 3600:   return f"{s // 60}m ago"
    if s < 86400:  return f"{s // 3600}h ago"
    if s < 604800: return f"{s // 86400}d ago"
    return dt.strftime("%b %d")


@login_required
def notifications_api(request):
    notifs = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).select_related('company', 'jobseeker', 'job')[:20]

    data = []
    for n in notifs:
        item = {
            'id': n.id,
            'type': n.notif_type,
            'created_at': _relative_time(n.created_at),
            'actor': '',
            'verb': '',
            'quoted': '',
            'meta': n.job.title if n.job else '',
            'icon': 'heart',
            'url': '#',
        }
        if n.notif_type == Notification.COMPANY_LIKED_YOU:
            item['actor'] = n.company.name if n.company else 'Employer'
            item['verb']  = 'liked your resume.'
            item['icon']  = 'heart'
            item['url']   = f'/jobs/view/{n.job.id}/' if n.job else '#'
        elif n.notif_type == Notification.MATCH:
            item['icon'] = 'sparkle'
            if request.user.is_jobseeker:
                item['actor'] = n.company.name if n.company else 'Employer'
                item['verb']  = "is a match!"
            else:
                item['actor'] = f"{n.jobseeker.first_name} {n.jobseeker.last_name}" if n.jobseeker else 'Jobseeker'
                item['verb']  = "is a match!"
            item['url'] = f'/jobs/view/{n.job.id}/' if n.job else '#'
        elif n.notif_type == Notification.JOBSEEKERS_LIKED_JOB:
            item['actor'] = n.liker_preview or 'Someone'
            item['verb']  = 'liked your job post.'
            item['icon']  = 'heart'
            item['url']   = f'/employers/jobs/{n.job.id}/candidates/?tab=liked_by' if n.job else '#'
        data.append(item)

    return JsonResponse({'notifications': data, 'count': len(data)})


@login_required
def mark_read(request, notif_id):
    if request.method == 'POST':
        Notification.objects.filter(id=notif_id, recipient=request.user).update(is_read=True)
    return JsonResponse({'ok': True})


@login_required
def mark_all_read(request):
    if request.method == 'POST':
        Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'ok': True})