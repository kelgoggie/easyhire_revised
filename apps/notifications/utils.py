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
    # Notify jobseeker
    Notification.objects.create(
        recipient=jobseeker.user,
        notif_type=Notification.MATCH,
        company=company,
        jobseeker=jobseeker,
        job=job,
    )
    # Notify employer
    Notification.objects.create(
        recipient=company.representatives.first().user,
        notif_type=Notification.MATCH,
        company=company,
        jobseeker=jobseeker,
        job=job,
    )


def refresh_jobseeker_liked_job_notification(job):
    """Recompute the single grouped 'X liked your job post' notification
    for this job's employer. Call after any like/un-like change.
    Stores just the name preview (e.g. 'Juan and Janice' or 'Juan and 14 others');
    the verb 'liked your job post.' is appended at render time."""
    from .models import Notification
    from apps.jobseekers.models import JobInteraction

    rep = job.company.representatives.first()
    if not rep or not rep.user:
        return
    employer_user = rep.user

    likers = list(
        JobInteraction.objects.filter(job=job, interaction_type=JobInteraction.LIKED)
        .select_related('jobseeker').order_by('created_at')
    )
    count = len(likers)

    existing = Notification.objects.filter(
        recipient=employer_user,
        notif_type=Notification.JOBSEEKERS_LIKED_JOB,
        job=job,
        is_read=False,
    ).first()

    if count == 0:
        if existing:
            existing.delete()
        return

    first = likers[0].jobseeker.first_name
    if count == 1:
        preview = first
    elif count == 2:
        preview = f"{first} and {likers[1].jobseeker.first_name}"
    else:
        others = count - 1
        preview = f"{first} and {others} other{'s' if others != 1 else ''}"

    if existing:
        existing.liker_count = count
        existing.liker_preview = preview
        existing.save(update_fields=['liker_count', 'liker_preview'])
    else:
        Notification.objects.create(
            recipient=employer_user,
            notif_type=Notification.JOBSEEKERS_LIKED_JOB,
            job=job,
            liker_count=count,
            liker_preview=preview,
        )


def notify_jobseeker_liked_job(jobseeker, job):
    refresh_jobseeker_liked_job_notification(job)