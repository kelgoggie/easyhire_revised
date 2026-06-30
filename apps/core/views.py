from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from apps.core.hashids import encode as _hashid
from .models import Province, CityMunicipality, Barangay


def help_view(request):
    """Help page. Open to everyone so a logged-out admin clicking the Help
    link doesn't get bounced to the jobseeker login. Picks template by role
    so the shell matches the visitor — critically, staff users get the
    admin shell, NOT the jobseeker one (which reads jobseeker_profile
    fields off the admin's user row and could surface stale data)."""
    user = request.user
    if user.is_authenticated:
        if getattr(user, 'is_staff', False):
            return render(request, 'admin_panel/help.html', {'active_nav': 'help'})
        if getattr(user, 'is_employer', False):
            return render(request, 'employers/help.html')
    return render(request, 'jobseekers/help.html')


@login_required
def inbox(request):
    """Unified inbox combining applications, interview schedules, and admin
    announcements. Forks by user type. Each item normalized to a common shape
    so the same template row renders all three sources.
    """
    from apps.admin_panel.models import AdminAnnouncement
    from apps.employers.models import EmployerContact
    from apps.jobs.models import Application
    from apps.core.pagination import paginate, querystring_without

    items = []
    user = request.user

    if user.is_jobseeker:
        try:
            profile = user.jobseeker_profile
        except Exception:
            return redirect('/register/info/')

        # Applications the jobseeker sent
        for app in (Application.objects
                    .filter(jobseeker=profile)
                    .select_related('job', 'job__company')):
            # Fall back gracefully if the job was deleted or its company removed.
            job_title = app.job.title if app.job else '(removed)'
            company_name = app.job.company.name if (app.job and app.job.company) else '(removed)'
            job_closed = bool(app.job and app.job.status == 'closed')
            job_link = (f'/jobs/view/{_hashid(app.job.id)}/'
                        if app.job and not job_closed else '')
            items.append({
                'kind': 'application_sent',
                'actor': 'You',
                'verb': f'applied to "{job_title}" at {company_name}.{ " (Job removed)" if not app.job else (" (Closed)" if job_closed else "") }',
                'context': app.status,
                'timestamp': app.created_at,
                'url': '/applications/',
                # Expandable detail panel: show the application message + a
                # "View job post" CTA. Empty message renders as a friendly note.
                'detail_body': app.message or '(No application message sent.)',
                'detail_cta_label': 'View job post' if job_link else '',
                'detail_cta_url':   job_link,
                'report_target_type': '',
                'report_target_id': None,
                'report_label': '',
            })

        # Employer contacts received (requirements + interview schedules).
        # Sender is rendered as "Company | Job Title" with two separate links
        # — company → public company profile, job → job post. The job link is
        # suppressed when the job has been removed (FK is SET_NULL on delete).
        for contact in (EmployerContact.objects
                        .filter(recipient=profile)
                        .select_related('company', 'sender', 'job')):
            sender_company_name = contact.company.name
            sender_company_url  = f'/companies/{_hashid(contact.company.id)}/'
            sender_job_title    = ''
            sender_job_url      = ''
            if contact.job:
                sender_job_title = contact.job.title
                # Closed jobs still have a public detail page; deleted jobs
                # come through here as None (SET_NULL) and just won't link.
                sender_job_url = f'/jobs/view/{_hashid(contact.job.id)}/'
            verb = (f'sent you {"interview details" if contact.kind == EmployerContact.KIND_INTERVIEW else "job requirements"}.')
            items.append({
                'kind': contact.kind,
                # Plain-text actor kept as a fallback for the row template /
                # screen readers; the template prefers the linked pair below.
                'actor': sender_company_name,
                'sender_company_name': sender_company_name,
                'sender_company_url':  sender_company_url,
                'sender_job_title':    sender_job_title,
                'sender_job_url':      sender_job_url,
                'verb': verb,
                'context': contact.subject,
                'timestamp': contact.sent_at,
                'url': '/inbox/',
                'detail_body': contact.body,
                'detail_interview_at': contact.interview_at,
                'detail_interview_location': contact.interview_location,
                'detail_company': contact.company.name,
                'report_target_type': 'employer',
                'report_target_id': contact.company.id,
                'report_label': f'Re: {contact.subject}',
            })

        # Admin announcements targeting jobseekers (or all)
        for ann in AdminAnnouncement.objects.filter(
            audience__in=[AdminAnnouncement.AUDIENCE_ALL, AdminAnnouncement.AUDIENCE_JOBSEEKERS]
        ):
            items.append({
                'kind': 'announcement',
                'actor': 'PESO Iloilo City',
                'verb': 'sent an announcement.',
                'context': ann.subject,
                'timestamp': ann.sent_at,
                'url': '/inbox/',
                'detail_body': ann.body,
                'report_target_type': '',
                'report_target_id': None,
                'report_label': '',
            })

        template = 'jobseekers/inbox.html'

    elif user.is_employer:
        try:
            employer_profile = user.employer_profile
        except Exception:
            return redirect('/employers/login/')
        company = employer_profile.company

        # Applications received on this company's job posts
        for app in (Application.objects
                    .filter(job__company=company)
                    .select_related('job', 'jobseeker', 'jobseeker__user')):
            # Resolve display + status flags up-front so the verb / link / CTA
            # all consistently signal a removed jobseeker or closed job.
            seeker_active = bool(app.jobseeker and app.jobseeker.user
                                 and app.jobseeker.user.is_active)
            jname = (f"{app.jobseeker.first_name} {app.jobseeker.last_name}".strip()
                     if app.jobseeker else 'User removed')
            if app.jobseeker and not seeker_active:
                jname = f"{jname} (deactivated)"
            job_title = app.job.title if app.job else '(removed)'
            job_closed = bool(app.job and app.job.status == 'closed')
            resume_link = (f'/employers/candidates/{_hashid(app.jobseeker.id)}/?job={_hashid(app.job.id)}'
                           if app.jobseeker and seeker_active and app.job else '')
            items.append({
                'kind': 'application_received',
                'actor': jname,
                'verb': f'sent a Job Application: "{job_title}".{ " (Closed)" if job_closed else "" }',
                'context': app.status,
                'timestamp': app.created_at,
                'url': resume_link or '/inbox/',
                # Expandable detail: application message + View Resume CTA.
                'detail_body': app.message or '(No application message sent.)',
                'detail_cta_label': 'View resume' if resume_link else '',
                'detail_cta_url':   resume_link,
                'report_target_type': 'jobseeker' if (app.jobseeker and seeker_active) else '',
                'report_target_id': app.jobseeker.id if (app.jobseeker and seeker_active) else None,
                'report_label': f'Re: application to {job_title}',
            })

        # Contacts the company has sent
        for contact in (EmployerContact.objects
                        .filter(company=company)
                        .select_related('recipient', 'job', 'sender')):
            jname = ''
            if contact.recipient:
                jname = f"{contact.recipient.first_name} {contact.recipient.last_name}".strip()
            kind_label = 'an Interview' if contact.kind == EmployerContact.KIND_INTERVIEW else 'Job Requirements'
            items.append({
                'kind': contact.kind,
                'actor': jname or 'Candidate',
                'verb': f'You scheduled {kind_label}.' if contact.kind == EmployerContact.KIND_INTERVIEW else f'You sent {kind_label}.',
                'context': contact.subject,
                'timestamp': contact.sent_at,
                'url': f'/employers/candidates/{_hashid(contact.recipient.id)}/' if contact.recipient else '/inbox/',
                'detail_body': contact.body,
                'detail_interview_at': contact.interview_at,
                'detail_interview_location': contact.interview_location,
                'report_target_type': '',
                'report_target_id': None,
                'report_label': '',
            })

        # Admin announcements targeting employers (or all)
        for ann in AdminAnnouncement.objects.filter(
            audience__in=[AdminAnnouncement.AUDIENCE_ALL, AdminAnnouncement.AUDIENCE_EMPLOYERS]
        ):
            items.append({
                'kind': 'announcement',
                'actor': 'PESO Iloilo City',
                'verb': 'sent an announcement.',
                'context': ann.subject,
                'timestamp': ann.sent_at,
                'url': '/inbox/',
                'detail_body': ann.body,
                'report_target_type': '',
                'report_target_id': None,
                'report_label': '',
            })

        # Account verification updates (verified / denied) — surfaced here
        # in addition to the banner on /employers/pending/.
        from apps.notifications.models import Notification
        for n in (Notification.objects
                  .filter(recipient=user, liker_preview='an account verification update')
                  .order_by('-created_at')):
            full = (n.admin_message or '').strip()
            subject, _, body = full.partition('\n\n')
            items.append({
                'kind': 'announcement',
                'actor': 'PESO Iloilo City',
                'verb': 'reviewed your verification.',
                'context': subject or 'Verification update',
                'timestamp': n.created_at,
                'url': '/employers/pending/',
                'detail_body': body or subject,
                'report_target_type': '',
                'report_target_id': None,
                'report_label': '',
            })

        template = 'employers/inbox.html'

    else:
        # Staff users — kick them to the admin panel where they compose announcements.
        return redirect('/admin-panel/announcements/')

    # Newest first
    items.sort(key=lambda x: x['timestamp'], reverse=True)
    total_items = len(items)

    # Snapshot BEFORE filtering so the sidebar dot tracks "anything new at all",
    # not "anything new in the currently selected filter".
    request.session['inbox_seen_count'] = total_items

    # ── Kind filter chips ───────────────────────────────────────────
    # Group the inbox's heterogeneous `kind` values into the four buckets
    # surfaced as chips. Anything outside these (e.g. a future kind) is
    # still in the All bucket but not reachable via a chip.
    KIND_GROUPS = {
        'announcements': {'announcement'},
        'applications':  {'application_sent', 'application_received'},
        'interviews':    {'interview'},
        'requirements':  {'requirements'},
    }
    kind_counts = {key: sum(1 for it in items if it['kind'] in members)
                   for key, members in KIND_GROUPS.items()}

    kind_filter = (request.GET.get('kind') or '').strip().lower()
    if kind_filter in KIND_GROUPS:
        items = [it for it in items if it['kind'] in KIND_GROUPS[kind_filter]]
    else:
        kind_filter = ''  # normalize unknown values to "All"

    page = paginate(request, items, per_page=15)

    return render(request, template, {
        'items': list(page.object_list),
        'page': page,
        # qs_base preserves `kind` across pagination clicks but drops `page`
        # so each chip click resets to page 1.
        'qs_base': querystring_without(request, 'page'),
        'kind_filter': kind_filter,
        'kind_counts': kind_counts,
        'total_items': total_items,
        'unread_notifications': False,
        'unread_messages': False,
    })


def _dedupe_locations(rows):
    """Keep one row per (lowercased name). PSGC loads have sometimes inserted
    duplicate rows (re-runs of load_psgc, mixed PSA snapshots); the unique
    key is on `code` not `name`, so two rows with different codes but the
    same name leak through .values() and surface as repeats in the UI."""
    seen = set()
    out = []
    for row in rows:
        key = (row.get('name') or '').strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def provinces_api(request):
    provinces = Province.objects.values('code', 'name').order_by('name')
    return JsonResponse(_dedupe_locations(provinces), safe=False)


def cities_api(request, province_code):
    cities = CityMunicipality.objects.filter(
        province__code=province_code
    ).values('code', 'name').order_by('name')
    return JsonResponse(_dedupe_locations(cities), safe=False)


def barangays_api(request, city_code):
    barangays = Barangay.objects.filter(
        city__code=city_code
    ).values('code', 'name').order_by('name')
    return JsonResponse(_dedupe_locations(barangays), safe=False)