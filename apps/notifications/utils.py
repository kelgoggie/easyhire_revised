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


def notify_jobseeker_liked_job(jobseeker, job):
    from .models import Notification
    from apps.jobseekers.models import JobInteraction

    employer_user = job.company.representatives.first().user
    if not employer_user:
        return

    # Get all likers for this job
    liked_profiles = list(
        JobInteraction.objects.filter(
            job=job, interaction_type='liked'
        ).select_related('jobseeker').order_by('created_at')
    )

    count = len(liked_profiles)
    if count == 0:
        return

    # Build preview text
    names = [f"{li.jobseeker.first_name}" for li in liked_profiles[:2]]
    if count > 2:
        preview = f"{', '.join(names)} and {count - 2}+ others liked your job"
    elif count == 2:
        preview = f"{names[0]} and {names[1]} liked your job"
    else:
        preview = f"{names[0]} liked your job"

    # Update existing grouped notification or create new one
    existing = Notification.objects.filter(
        recipient=employer_user,
        notif_type=Notification.JOBSEEKERS_LIKED_JOB,
        job=job,
        is_read=False,
    ).first()

    if existing:
        existing.liker_count = count
        existing.liker_preview = preview
        existing.save()
    else:
        Notification.objects.create(
            recipient=employer_user,
            notif_type=Notification.JOBSEEKERS_LIKED_JOB,
            job=job,
            liker_count=count,
            liker_preview=preview,
        )