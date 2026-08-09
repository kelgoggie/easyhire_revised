from django.shortcuts import render

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.core.hashids import encode as _hashid
from .models import Notification


def _relative_time(dt):
    s = int((timezone.now() - dt).total_seconds())
    if s < 60:     return f"{max(s, 1)}s ago"
    if s < 3600:   return f"{s // 60}m ago"
    if s < 86400:  return f"{s // 3600}h ago"
    if s < 604800: return f"{s // 86400}d ago"
    return dt.strftime("%b %d")


# Notifications that also land in the user's Inbox (or are otherwise
# message-shaped: application arrivals, employer messages, admin
# announcements, invitations to apply) belong in the mail-icon dropdown.
# Everything else (matches, likes, hire flow, status changes) stays on
# the bell. Kelly wants Invited-to-Apply on the mail side even though
# there's no inbox row for it — it reads as a personal message to the
# jobseeker.
MAIL_BUCKET_TYPES = {
    Notification.NEW_APPLICATION,
    Notification.NEW_ANNOUNCEMENT,
    Notification.EMPLOYER_CONTACTED,
    Notification.INVITED_TO_APPLY,
    # PESO take-down notices carry a reason the employer needs to read,
    # not just a status ping — the mail dropdown gives them more visual
    # weight and matches where an announcement-style message belongs.
    Notification.JOB_DELETED_BY_ADMIN,
}


@login_required
def notifications_api(request):
    # Bell + mail dropdown both render off this feed — most recent 20
    # notifications regardless of read state so users can revisit what
    # they've seen. Each item ships with a `bucket` field ('mail' or
    # 'bell') the client uses to split the list into the two icons.
    notifs = Notification.objects.filter(
        recipient=request.user
    ).select_related('company', 'jobseeker', 'job').order_by('-created_at')[:20]

    data = []
    unread_bell = 0
    unread_mail = 0
    for n in notifs:
        bucket = 'mail' if n.notif_type in MAIL_BUCKET_TYPES else 'bell'
        if not n.is_read:
            if bucket == 'mail':
                unread_mail += 1
            else:
                unread_bell += 1
        item = {
            # Encoded so the front-end fetch hits the <hashid:notif_id> URL
            # pattern correctly. Passing the raw int silently 404s.
            'id': _hashid(n.id),
            'type': n.notif_type,
            'bucket': bucket,
            'created_at': _relative_time(n.created_at),
            'is_read': n.is_read,
            'actor': '',
            'verb': '',
            'quoted': '',
            'meta': n.job.title if n.job else '',
            'icon': 'heart',
            'url': '#',
            'hire_app_hashid': '',  # set below for HIRE_OFFERED so the jobseeker
                                    # can Accept/Decline inline from the bell.
        }
        if n.notif_type == Notification.COMPANY_LIKED_YOU:
            item['actor'] = n.company.name if n.company else 'Employer'
            item['verb']  = 'bookmarked your résumé.'
            item['icon']  = 'heart'
            item['url']   = f'/jobs/view/{_hashid(n.job.id)}/' if n.job else '#'
        elif n.notif_type == Notification.MATCH:
            item['icon'] = 'sparkle'
            if request.user.is_jobseeker:
                item['actor'] = n.company.name if n.company else 'Employer'
                item['verb']  = "is a match!"
            else:
                item['actor'] = f"{n.jobseeker.first_name} {n.jobseeker.last_name}" if n.jobseeker else 'Jobseeker'
                item['verb']  = "is a match!"
            item['url'] = f'/jobs/view/{_hashid(n.job.id)}/' if n.job else '#'
        elif n.notif_type == Notification.JOBSEEKERS_LIKED_JOB:
            item['actor'] = n.liker_preview or 'Someone'
            item['verb']  = 'bookmarked your job post.'
            item['icon']  = 'heart'
            item['url']   = f'/employers/jobs/{_hashid(n.job.id)}/candidates/?tab=liked_by' if n.job else '#'
        elif n.notif_type == Notification.JOB_DELETED_BY_ADMIN:
            # This notif_type covers admin take-downs — currently that's
            # the disable flow (admin_job_disable in admin_panel/views).
            # Wording says "disabled" to match the actual state change:
            # the job is closed + admin_disabled=True, not deleted.
            item['actor']  = 'PESO Admin'
            item['verb']   = f'disabled your job post "{n.liker_preview or "Untitled"}".'
            item['quoted'] = n.admin_message or 'No reason provided.'
            item['icon']   = 'warning'
            item['meta']   = ''
            item['url']    = '/employers/jobs/' if n.recipient.is_employer else '#'
        elif n.notif_type == Notification.PERSONAL_INFO_APPROVED:
            item['actor'] = 'PESO Admin'
            item['verb']  = 'approved your personal information change request.'
            item['icon']  = 'check'
            item['meta']  = ''
            item['url']   = '/settings/'
        elif n.notif_type == Notification.PERSONAL_INFO_REJECTED:
            item['actor'] = 'PESO Admin'
            item['verb']  = 'denied your personal information change request.'
            item['icon']  = 'xmark'
            item['meta']  = ''
            item['url']   = '/settings/'
        elif n.notif_type == Notification.ID_VERIFICATION_APPROVED:
            item['actor'] = 'PESO Admin'
            item['verb']  = 'approved your ID verification. You now have the PESO Verified badge.'
            item['icon']  = 'check'
            item['meta']  = ''
            item['url']   = '/settings/'
        elif n.notif_type == Notification.ID_VERIFICATION_DENIED:
            item['actor']  = 'PESO Admin'
            item['verb']   = 'denied your ID verification. Please review the note and resubmit.'
            item['quoted'] = n.admin_message or ''
            item['icon']   = 'xmark'
            item['meta']   = ''
            item['url']    = '/settings/verify-id/'
        elif n.notif_type == Notification.NEW_APPLICATION:
            # `liker_preview` carries the grouped label ("X and 2 others")
            # when set by notify_new_application. Falls back to the latest
            # applicant's name for legacy rows created before the group
            # helper landed.
            actor_name = (n.liker_preview
                          or (f'{n.jobseeker.first_name} {n.jobseeker.last_name}'
                              if n.jobseeker else 'Someone'))
            item['actor'] = actor_name
            job_title = n.job.title if n.job else 'your job post'
            item['verb']  = f'applied to {job_title}.' if (n.liker_count or 1) == 1 else f'applied to your job post: {job_title}'
            item['icon']  = 'briefcase'
            item['url']   = (f'/employers/jobs/{_hashid(n.job.id)}/candidates/?tab=applicants'
                             if n.job else '/employers/jobs/')
        elif n.notif_type == Notification.APPLICATION_ACCEPTED:
            item['actor'] = n.company.name if n.company else 'Employer'
            item['verb']  = 'is moving forward with your application.'
            item['icon']  = 'check'
            item['url']   = '/applications/'
        elif n.notif_type == Notification.APPLICATION_REJECTED:
            item['actor'] = n.company.name if n.company else 'Employer'
            item['verb']  = 'declined your application.'
            item['icon']  = 'xmark'
            item['url']   = '/applications/'
        elif n.notif_type == Notification.APPLICATION_HIRED:
            item['actor'] = n.company.name if n.company else 'Employer'
            item['verb']  = 'hired you — congratulations!'
            item['icon']  = 'sparkle'
            item['url']   = '/applications/'
        elif n.notif_type == Notification.HIRE_OFFERED:
            item['actor'] = n.company.name if n.company else 'An employer'
            job_title = n.job.title if n.job else 'a position'
            item['verb']  = f'sent you a job offer for {job_title}.'
            item['icon']  = 'briefcase'
            # Find the underlying application so the inline Accept/Decline
            # buttons can target it. Bell renders these buttons when
            # `hire_app_hashid` is non-empty.
            from apps.jobs.models import Application
            if n.jobseeker and n.job:
                app = Application.objects.filter(
                    jobseeker=n.jobseeker, job=n.job,
                    status=Application.STATUS_HIRE_PENDING,
                ).first()
                if app:
                    item['hire_app_hashid'] = _hashid(app.id)
            item['url'] = '/applications/'
        elif n.notif_type == Notification.HIRE_ACCEPTED:
            who = (f"{n.jobseeker.first_name} {n.jobseeker.last_name}"
                   if n.jobseeker else 'The jobseeker')
            item['actor'] = who
            item['verb']  = 'accepted your job offer.'
            item['icon']  = 'sparkle'
            item['url']   = (f'/employers/jobs/{_hashid(n.job.id)}/candidates/?tab=applicants&status=hired'
                             if n.job else '/employers/jobs/')
        elif n.notif_type == Notification.HIRE_DECLINED:
            who = (f"{n.jobseeker.first_name} {n.jobseeker.last_name}"
                   if n.jobseeker else 'The jobseeker')
            item['actor'] = who
            item['verb']  = 'declined your job offer.'
            item['icon']  = 'xmark'
            item['url']   = (f'/employers/jobs/{_hashid(n.job.id)}/candidates/?tab=applicants'
                             if n.job else '/employers/jobs/')
        elif n.notif_type == Notification.APPLICATION_UNHIRED:
            item['actor'] = n.company.name if n.company else 'An employer'
            job_title = n.job.title if n.job else 'a role'
            item['verb'] = f'marked your employment as ended for {job_title}.'
            item['icon'] = 'warning'
            item['url']  = '/applications/'
        elif n.notif_type == Notification.EMPLOYER_CONTACTED:
            item['actor']  = n.company.name if n.company else 'An employer'
            # Drop "Check your email" — for test / demo accounts SMTP is
            # skipped, and even on real accounts the in-app inbox is the
            # source of truth. The message body is under Inbox → open row.
            item['verb']   = f'sent you {n.liker_preview or "a message"}.'
            item['quoted'] = n.admin_message or ''
            item['icon']   = 'envelope'
            item['url']    = '/inbox/'
        elif n.notif_type == Notification.NEW_ANNOUNCEMENT:
            # PESO admin broadcast. Subject line lives in liker_preview; the
            # full body sits in the recipient's Inbox row alongside older
            # announcements. Click sends them straight to Inbox.
            item['actor']  = 'PESO Iloilo City'
            item['verb']   = f'sent an announcement: {n.liker_preview or ""}'.strip()
            item['icon']   = 'megaphone'
            item['meta']   = ''
            item['url']    = '/inbox/'
        elif n.notif_type == Notification.INVITED_TO_APPLY:
            # Lightweight nudge — no inbox row, no email. Verb reads as
            # "{Company} invited you to apply for {Job Title}." and the
            # notification itself is the whole payload; clicking it takes
            # the jobseeker straight to the job detail so they can Apply.
            item['actor'] = n.company.name if n.company else 'An employer'
            job_title = n.job.title if n.job else 'a role'
            item['verb'] = f'invited you to apply for {job_title}.'
            item['icon'] = 'briefcase'
            item['url']  = f'/jobs/view/{_hashid(n.job.id)}/' if n.job else '/jobs/'
        data.append(item)

    return JsonResponse({
        'notifications': data,
        'count':         len(data),
        # Legacy total — kept for any client still reading it.
        'unread_count':  unread_bell + unread_mail,
        # Split counts for the two dropdowns (bell + mail).
        'unread_bell':   unread_bell,
        'unread_mail':   unread_mail,
    })


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