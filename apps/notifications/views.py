from django.shortcuts import render

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Notification


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
            'created_at': n.created_at.strftime('%b %d, %I:%M %p'),
        }
        if n.notif_type == Notification.COMPANY_LIKED_YOU:
            item['text'] = f"{n.company.name} liked you"
            item['subtext'] = n.job.title if n.job else ''
            item['url'] = f'/jobs/view/{n.job.id}/' if n.job else '#'
        elif n.notif_type == Notification.MATCH:
            if request.user.is_jobseeker:
                item['text'] = f"You matched with {n.company.name}!"
            else:
                item['text'] = f"{n.jobseeker.first_name} {n.jobseeker.last_name} is a match!"
            item['subtext'] = n.job.title if n.job else ''
            item['url'] = f'/jobs/view/{n.job.id}/' if n.job else '#'
        elif n.notif_type == Notification.JOBSEEKERS_LIKED_JOB:
            item['text'] = n.liker_preview
            item['subtext'] = n.job.title if n.job else ''
            item['url'] = f'/employers/jobs/{n.job.id}/candidates/?tab=liked_by' if n.job else '#'
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