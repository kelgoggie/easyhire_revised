from apps.accounts.models import User


def notify_company_liked_jobseeker(company, jobseeker, job):
    from .models import Notification
    Notification.objects.create(
        recipient=jobseeker.user,
        notif_type=Notification.COMPANY_LIKED_YOU,
        company=company,
        jobseeker=jobseeker,
        job=job,
    )


def notify_match(company, jobseeker, job):
    from .models import Notification
    # Notify the jobseeker (single user)
    Notification.objects.create(
        recipient=jobseeker.user,
        notif_type=Notification.MATCH,
        company=company,
        jobseeker=jobseeker,
        job=job,
    )
    # Notify every company representative
    for rep in company.representatives.select_related('user'):
        Notification.objects.create(
            recipient=rep.user,
            notif_type=Notification.MATCH,
            company=company,
            jobseeker=jobseeker,
            job=job,
        )


def refresh_jobseeker_liked_job_notification(job):
    """Recompute the grouped 'X liked your job post' notification for every
    representative of this job's company. Call after any like/un-like change.
    Stores just the name preview (e.g. 'Juan and Janice' or 'Juan and 14 others');
    the verb 'liked your job post.' is appended at render time."""
    from .models import Notification
    from apps.jobseekers.models import JobInteraction

    reps = list(job.company.representatives.select_related('user'))
    if not reps:
        return

    likers = list(
        JobInteraction.objects.filter(job=job, interaction_type=JobInteraction.LIKED)
        .select_related('jobseeker').order_by('created_at')
    )
    count = len(likers)

    if count == 0:
        # Remove any stale unread notifications for all reps.
        Notification.objects.filter(
            recipient__in=[r.user for r in reps],
            notif_type=Notification.JOBSEEKERS_LIKED_JOB,
            job=job,
            is_read=False,
        ).delete()
        return

    first = likers[0].jobseeker.first_name
    if count == 1:
        preview = first
    elif count == 2:
        preview = f"{first} and {likers[1].jobseeker.first_name}"
    else:
        others = count - 1
        preview = f"{first} and {others} other{'s' if others != 1 else ''}"

    for rep in reps:
        existing = Notification.objects.filter(
            recipient=rep.user,
            notif_type=Notification.JOBSEEKERS_LIKED_JOB,
            job=job,
            is_read=False,
        ).first()
        if existing:
            existing.liker_count = count
            existing.liker_preview = preview
            existing.save(update_fields=['liker_count', 'liker_preview'])
        else:
            Notification.objects.create(
                recipient=rep.user,
                notif_type=Notification.JOBSEEKERS_LIKED_JOB,
                job=job,
                liker_count=count,
                liker_preview=preview,
            )


def notify_jobseeker_liked_job(jobseeker, job):
    refresh_jobseeker_liked_job_notification(job)