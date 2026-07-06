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

    def _full_name(p):
        return f"{p.first_name} {p.last_name}".strip() or p.first_name or 'Someone'

    first = _full_name(likers[0].jobseeker)
    if count == 1:
        preview = first
    elif count == 2:
        preview = f"{first} and {_full_name(likers[1].jobseeker)}"
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


def notify_high_match_jobseekers(job, threshold=80):
    """When a new job is posted, notify every jobseeker whose match score
    against it clears `threshold` (default 80). Uses the existing MATCH
    notification type since the semantic is the same — a strong match
    between this jobseeker and this job — but with the actor set to the
    company.

    Called from job_create after the job's requirements have been saved.
    Guarded by profile.profile_complete so we don't spam users who still
    have empty resumes (their scores would be near-zero anyway).
    """
    from .models import Notification
    from apps.jobseekers.models import JobseekerProfile
    from apps.matching.engine import compute_match_score

    profiles = JobseekerProfile.objects.filter(
        profile_complete=True, user__isnull=False,
    ).select_related('user')
    for profile in profiles:
        try:
            score = compute_match_score(job, profile)
            total = score['total'] if isinstance(score, dict) else score
        except Exception:
            continue
        if total is None or total < threshold:
            continue
        Notification.objects.create(
            recipient=profile.user,
            notif_type=Notification.MATCH,
            company=job.company,
            jobseeker=profile,
            job=job,
        )


def notify_company_followed(company, jobseeker):
    """Notify every rep of `company` that `jobseeker` just followed them.
    Uses COMPANY_LIKED_YOU as a shared "someone showed interest" bucket —
    kept type-agnostic on purpose so we don't churn migrations for what's
    functionally the same notification.
    """
    from .models import Notification
    for rep in company.representatives.select_related('user'):
        if rep.user:
            Notification.objects.create(
                recipient=rep.user,
                notif_type=Notification.JOBSEEKERS_LIKED_JOB,
                company=company,
                jobseeker=jobseeker,
                liker_count=1,
                liker_preview=f"{jobseeker.first_name} {jobseeker.last_name}".strip()
                              + " started following your company",
            )