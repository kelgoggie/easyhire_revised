"""Template context processors for the core app."""


def inbox_status(request):
    """Expose ``inbox_has_new`` to every authenticated template so the
    sidebar Inbox link can render a dot when something new has arrived.

    Strategy: compare the current count of inbox items against the
    snapshot the user saw on their last visit (stored in the session).
    A higher current count → dot. The inbox view itself updates the
    snapshot on render so the dot clears the moment they open it.

    Keeping this in the session avoids a schema change for a UI hint;
    the trade-off is the dot resets when the session expires, which is
    acceptable for a thesis demo.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'inbox_has_new': False}

    try:
        current = _count_inbox_items(user)
    except Exception:
        return {'inbox_has_new': False}

    seen = request.session.get('inbox_seen_count', 0)
    return {
        'inbox_has_new': current > seen,
        'inbox_total':   current,
    }


def _count_inbox_items(user):
    """Lightweight count — mirrors the kinds of items inbox() renders for
    each user type. Uses COUNT(*) queries rather than building full rows."""
    from apps.admin_panel.models import AdminAnnouncement
    from apps.employers.models import EmployerContact
    from apps.jobs.models import Application

    if getattr(user, 'is_jobseeker', False):
        try:
            profile = user.jobseeker_profile
        except Exception:
            return 0
        return (
            Application.objects.filter(jobseeker=profile).count()
            + EmployerContact.objects.filter(recipient=profile).count()
            + AdminAnnouncement.objects.filter(
                audience__in=[AdminAnnouncement.AUDIENCE_ALL, AdminAnnouncement.AUDIENCE_JOBSEEKERS]
            ).count()
        )

    if getattr(user, 'is_employer', False):
        try:
            company = user.employer_profile.company
        except Exception:
            return 0
        from apps.notifications.models import Notification
        return (
            Application.objects.filter(job__company=company).count()
            + EmployerContact.objects.filter(company=company).count()
            + AdminAnnouncement.objects.filter(
                audience__in=[AdminAnnouncement.AUDIENCE_ALL, AdminAnnouncement.AUDIENCE_EMPLOYERS]
            ).count()
            + Notification.objects.filter(
                recipient=user,
                liker_preview='an account verification update',
            ).count()
        )

    return 0
