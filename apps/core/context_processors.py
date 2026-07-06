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

    # On the FIRST check within a session, baseline the "seen" count to
    # the current total so pre-existing items (like seeded applications)
    # don't fire the "new" dot immediately. Real new activity that lands
    # AFTER login still flips the dot on because current will exceed
    # this initial baseline.
    if 'inbox_seen_count' not in request.session:
        request.session['inbox_seen_count'] = current
        return {'inbox_has_new': False, 'inbox_total': current}

    seen = request.session.get('inbox_seen_count', 0)
    return {
        'inbox_has_new': current > seen,
        'inbox_total':   current,
    }


def notifications_baseline(request):
    """Mark stale unread notifications as read on the user's first
    authenticated hit of a session. Seeded / carryover activity from long
    before this session shouldn't buzz the bell.

    Guarded by a GRACE_PERIOD so notifications created within the last
    15 minutes are never baselined — even if they technically pre-date
    this login. That covers the common demo flow: employer sends an offer,
    logs out, jobseeker logs in a moment later. Without the grace period
    the just-sent offer would be silently marked read and the jobseeker
    would never see it.

    Combined guard: baseline only when the notification is BOTH older
    than the user's last_login AND older than GRACE_PERIOD.
    """
    from datetime import timedelta
    from django.utils import timezone as _tz
    GRACE_PERIOD = timedelta(minutes=15)

    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    if request.session.get('notif_baselined'):
        return {}
    try:
        from apps.notifications.models import Notification
        cutoff = _tz.now() - GRACE_PERIOD
        # If we have a last_login, cap the cutoff at whichever is EARLIER
        # (older) — that way a user who's been logged out for hours doesn't
        # accidentally baseline notifications from the last 15 min AFTER
        # login. The grace period is a floor, not a ceiling.
        if user.last_login and user.last_login < cutoff:
            cutoff = user.last_login
        Notification.objects.filter(
            recipient=user, is_read=False, created_at__lt=cutoff,
        ).update(is_read=True)
    except Exception:
        pass
    request.session['notif_baselined'] = True
    return {}


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
