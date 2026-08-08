from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from apps.core.hashids import encode as _hashid
from .models import Province, CityMunicipality, Barangay


def help_view(request):
    """Help page. FAQ content is DB-backed (apps.admin_panel.models.FAQ)
    so PESO staff can edit it via /admin-panel/faqs/ without a code change.
    Staff themselves don't get a help page — they land on the FAQ manager
    where they can preview + edit both audience's questions in one place."""
    from apps.admin_panel.models import FAQ

    user = request.user
    if user.is_authenticated and getattr(user, 'is_staff', False):
        return redirect('/admin-panel/faqs/')

    is_employer = user.is_authenticated and getattr(user, 'is_employer', False)
    audience_filter = [FAQ.AUDIENCE_EMPLOYER, FAQ.AUDIENCE_BOTH] if is_employer \
        else [FAQ.AUDIENCE_JOBSEEKER, FAQ.AUDIENCE_BOTH]
    faqs = FAQ.objects.filter(is_published=True, audience__in=audience_filter)

    template = 'employers/help.html' if is_employer else 'jobseekers/help.html'
    return render(request, template, {'faqs': faqs})


_INTERVIEW_PREFIXES = (
    # (prefix stored on EmployerContact.interview_location, canonical kind)
    ('Office: ',          'onsite'),
    ('Online meeting: ',  'online'),
    ('Phone call: ',      'phone'),
)


def _parse_interview_location(raw):
    """Split the stored `interview_location` string back into (kind, value).

    Employers compose interviews via a radio + a single text field; the
    submit handler prefixes the value with 'Office: ' / 'Online meeting: '
    / 'Phone call: ' so `EmployerContact.interview_location` is a single
    column. Here we invert that so the inbox letter-view can label the
    line correctly ("Venue" / "Link" / "Phone Number") and print just
    the value without the prefix.
    """
    if not raw:
        return ('', '')
    for prefix, kind in _INTERVIEW_PREFIXES:
        if raw.startswith(prefix):
            return (kind, raw[len(prefix):].strip())
    return ('', raw.strip())


def _employer_display_name(contact):
    """Best-effort sender name for the interview letter closing.
    Falls back to empty when the sender was removed or lacks a profile;
    the company name is always rendered below either way.
    """
    if not contact.sender_id:
        return ''
    try:
        prof = contact.sender.employer_profile
    except Exception:
        return ''
    parts = [prof.first_name or '', prof.last_name or '']
    return ' '.join(p for p in parts if p).strip()


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
                'source_type': 'application',
                'source_id': app.id,
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
            interview_kind, interview_value = _parse_interview_location(contact.interview_location)
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
                # Letter-view enrichment for the interview detail block:
                # `_inbox_rows.html` uses these to render Dear/schedule/thanks.
                'detail_interview_kind':  interview_kind,     # 'onsite'/'online'/'phone'/''
                'detail_interview_value': interview_value,    # prefix stripped
                'detail_recipient_name':  profile.first_name or '',
                'detail_sender_name':     _employer_display_name(contact),
                'detail_company': contact.company.name,
                # Reports on inbox messages target the specific EmployerContact
                # (the message itself) so an admin lands on the message body
                # in question — the sending company can still be disabled from
                # the message viewer's quick-actions.
                'report_target_type': 'contact',
                'report_target_id': contact.id,
                'report_label': f'Re: {contact.subject}',
                'source_type': 'contact',
                'source_id': contact.id,
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
                'source_type': 'announcement',
                'source_id': ann.id,
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
                'detail_cta_label': 'View résumé' if resume_link else '',
                'detail_cta_url':   resume_link,
                'report_target_type': 'jobseeker' if (app.jobseeker and seeker_active) else '',
                'report_target_id': app.jobseeker.id if (app.jobseeker and seeker_active) else None,
                'report_label': f'Re: application to {job_title}',
                'source_type': 'application',
                'source_id': app.id,
            })

        # Contacts the company has sent
        for contact in (EmployerContact.objects
                        .filter(company=company)
                        .select_related('recipient', 'job', 'sender')):
            jname = ''
            if contact.recipient:
                jname = f"{contact.recipient.first_name} {contact.recipient.last_name}".strip()
            kind_label = 'an Interview' if contact.kind == EmployerContact.KIND_INTERVIEW else 'Job Requirements'
            interview_kind, interview_value = _parse_interview_location(contact.interview_location)
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
                # Same letter-view enrichment the jobseeker branch adds — so
                # the employer viewing their own outbound copy sees exactly
                # what the jobseeker sees.
                'detail_interview_kind':  interview_kind,
                'detail_interview_value': interview_value,
                'detail_recipient_name':  (contact.recipient.first_name if contact.recipient else '') or '',
                'detail_sender_name':     _employer_display_name(contact),
                'detail_company':         contact.company.name,
                # Delivery status — populated by notifications.email._send()
                # only when the SMTP handoff succeeds. Rendered as a small
                # "Sent · delivered to X" / "Delivery pending" line on the
                # inbox row so the employer can see at a glance whether
                # their message actually went out.
                'delivered_to_email': contact.delivered_to_email or '',
                # Marks this row as the sender's own outbound copy. The inbox
                # row template only renders the delivery indicator for
                # is_outgoing rows — jobseekers seeing an incoming message
                # shouldn't care whether the employer's SMTP handoff worked.
                'is_outgoing': True,
                'report_target_type': '',
                'report_target_id': None,
                'report_label': '',
                'source_type': 'contact',
                'source_id': contact.id,
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
                'source_type': 'announcement',
                'source_id': ann.id,
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
                'source_type': 'verification',
                'source_id': n.id,
            })

        template = 'employers/inbox.html'

    else:
        # Staff users — kick them to the admin panel where they compose announcements.
        return redirect('/admin-panel/announcements/')

    # ── Per-user overlay: dismissed + pinned ───────────────────────────
    # One query fetches every state row for this user; we map by
    # (source_type, source_id) so item lookup is O(1). Rows the user has
    # dismissed are dropped completely (or shown alone on the Deleted
    # tab); pinned rows are tagged and float above the timestamp sort.
    from apps.core.models import InboxUserState
    from datetime import timedelta as _timedelta
    from django.utils import timezone as _tz2
    # Auto-purge: delete dismissed rows older than 30 days on every inbox
    # render. Cheap (one indexed DELETE) and runs on the user's own visit
    # so no cron/management-command is needed for the 30-day sweep.
    InboxUserState.objects.filter(
        user=user, is_dismissed=True,
        updated_at__lt=_tz2.now() - _timedelta(days=30),
    ).delete()
    state_rows = InboxUserState.objects.filter(user=user).values(
        'source_type', 'source_id', 'is_dismissed', 'is_pinned',
    )
    state_map = {(r['source_type'], r['source_id']): r for r in state_rows}
    def _state_key(it): return (it.get('source_type', ''), it.get('source_id', 0))
    # Deleted-tab support: ?kind=deleted flips the filter so we render ONLY
    # dismissed rows (up to 30 days back, per the purge above). All other
    # filters exclude dismissed rows as before.
    _show_deleted = (request.GET.get('kind') or '').strip().lower() == 'deleted'
    if _show_deleted:
        items = [it for it in items if state_map.get(_state_key(it), {}).get('is_dismissed')]
    else:
        items = [it for it in items if not state_map.get(_state_key(it), {}).get('is_dismissed')]
    for it in items:
        it['is_pinned']    = bool(state_map.get(_state_key(it), {}).get('is_pinned'))
        it['is_dismissed'] = bool(state_map.get(_state_key(it), {}).get('is_dismissed'))

    # Sort: user-selectable via ?sort=latest|oldest. Default is latest
    # first, which matches the pre-sort-control behavior. Pinned rows
    # always float to the top regardless of sort direction so the user
    # can find them without scrolling.
    sort = (request.GET.get('sort') or 'latest').strip().lower()
    if sort not in {'latest', 'oldest'}:
        sort = 'latest'
    items.sort(key=lambda x: (
        0 if x.get('is_pinned') else 1,
        (-x['timestamp'].timestamp()) if sort == 'latest' else x['timestamp'].timestamp(),
    ))
    total_items = len(items)

    # Per-row "unread" flag: an item is unread if it arrived AFTER the user's
    # last login (or after the session's `inbox_last_seen_at` — which we bump
    # on inbox render below, so a second visit within the same session doesn't
    # keep marking already-seen rows as unread).
    from django.utils import timezone as _tz
    last_seen_iso = request.session.get('inbox_last_seen_at')
    if last_seen_iso:
        try:
            from datetime import datetime
            last_seen_at = datetime.fromisoformat(last_seen_iso)
        except (TypeError, ValueError):
            last_seen_at = user.last_login
    else:
        last_seen_at = user.last_login
    for it in items:
        ts = it.get('timestamp')
        it['is_unread'] = bool(last_seen_at and ts and ts > last_seen_at)

    # Snapshot BEFORE filtering so the sidebar dot tracks "anything new at all",
    # not "anything new in the currently selected filter".
    request.session['inbox_seen_count'] = total_items
    # Bump the last-seen timestamp so per-row unread dots clear on next visit.
    # We do it AFTER computing is_unread above so the current render still
    # shows the dots — they'll clear on the next inbox load.
    request.session['inbox_last_seen_at'] = _tz.now().isoformat()

    # ── Text search ────────────────────────────────────────────────
    # Substring match (case-insensitive) across the text a user is likely
    # to remember from an inbox row: actor / verb / context / detail body
    # and, for jobseeker rows, the linked company + job title.
    search = (request.GET.get('q') or '').strip()
    if search:
        needle = search.lower()

        def _matches(it):
            haystack = ' '.join(str(it.get(k) or '') for k in (
                'actor', 'verb', 'context', 'detail_body',
                'sender_company_name', 'sender_job_title',
                'detail_company', 'detail_interview_location',
            ))
            return needle in haystack.lower()

        items = [it for it in items if _matches(it)]

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
    # Kind counts reflect the search-filtered view so the chip badges show
    # "how many of each kind match my search", not the pre-search totals.
    kind_counts = {key: sum(1 for it in items if it['kind'] in members)
                   for key, members in KIND_GROUPS.items()}
    # Deleted count comes straight from the state table (independent of the
    # normal item list, which excludes dismissed rows on the default tab).
    deleted_count = InboxUserState.objects.filter(
        user=user, is_dismissed=True,
    ).count()

    kind_filter = (request.GET.get('kind') or '').strip().lower()
    if kind_filter in KIND_GROUPS:
        items = [it for it in items if it['kind'] in KIND_GROUPS[kind_filter]]
    elif kind_filter == 'deleted':
        # No further sub-filtering — items already contains only dismissed
        # rows via the _show_deleted branch above.
        pass
    else:
        kind_filter = ''  # normalize unknown values to "All"

    # `filtered_total` is the total after search but before the kind chip —
    # drives the "All (N)" badge.
    filtered_total = sum(kind_counts.values()) if search else total_items

    page = paginate(request, items, per_page=15)

    return render(request, template, {
        'items': list(page.object_list),
        'page': page,
        # qs_base preserves `kind` + `q` + `sort` across pagination clicks
        # but drops `page` so each chip click resets to page 1.
        'qs_base': querystring_without(request, 'page'),
        'kind_filter': kind_filter,
        'kind_counts': kind_counts,
        'deleted_count': deleted_count,
        'total_items': filtered_total,
        'sort': sort,
        'search': search,
        'unread_notifications': False,
        'unread_messages': False,
    })


# ── Inbox row actions ─────────────────────────────────────────────
# Dismiss / pin / bulk-dismiss share one model (InboxUserState) so the
# three-dots menu and multi-select bar write to a single table. Views
# accept (source_type, source_id) pairs; the caller is responsible for
# sending the correct pair from the row's data attributes.
_VALID_SOURCES = {'application', 'contact', 'announcement', 'verification'}


def _upsert_inbox_state(user, source_type, source_id, **fields):
    """Get-or-create the state row and update the passed booleans."""
    from apps.core.models import InboxUserState
    state, _ = InboxUserState.objects.get_or_create(
        user=user, source_type=source_type, source_id=int(source_id),
    )
    updates = []
    for k, v in fields.items():
        if getattr(state, k) != v:
            setattr(state, k, v)
            updates.append(k)
    if updates:
        state.save(update_fields=updates + ['updated_at'])
    return state


@login_required
def inbox_dismiss(request):
    """Hide a single inbox row from THIS user's inbox. The underlying
    Application / EmployerContact / AdminAnnouncement is untouched — the
    other party still sees their own copy."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    st = (request.POST.get('source_type') or '').strip().lower()
    sid = (request.POST.get('source_id') or '').strip()
    if st not in _VALID_SOURCES or not sid.isdigit():
        return JsonResponse({'ok': False, 'error': 'Bad source'}, status=400)
    _upsert_inbox_state(request.user, st, sid, is_dismissed=True)
    return JsonResponse({'ok': True})


@login_required
def inbox_restore(request):
    """Undo a previous dismiss — used by the Restore action on the
    Deleted tab. Clears the is_dismissed flag on the user's state row so
    the item reappears in the normal inbox on next load."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    st = (request.POST.get('source_type') or '').strip().lower()
    sid = (request.POST.get('source_id') or '').strip()
    if st not in _VALID_SOURCES or not sid.isdigit():
        return JsonResponse({'ok': False, 'error': 'Bad source'}, status=400)
    _upsert_inbox_state(request.user, st, sid, is_dismissed=False)
    return JsonResponse({'ok': True})


@login_required
def inbox_pin(request):
    """Toggle pin on a single inbox row. Pinned rows float above the
    timestamp sort in the user's own inbox only."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    st = (request.POST.get('source_type') or '').strip().lower()
    sid = (request.POST.get('source_id') or '').strip()
    if st not in _VALID_SOURCES or not sid.isdigit():
        return JsonResponse({'ok': False, 'error': 'Bad source'}, status=400)
    from apps.core.models import InboxUserState
    existing = InboxUserState.objects.filter(
        user=request.user, source_type=st, source_id=int(sid),
    ).first()
    new_pinned = not (existing and existing.is_pinned)
    _upsert_inbox_state(request.user, st, sid, is_pinned=new_pinned)
    return JsonResponse({'ok': True, 'is_pinned': new_pinned})


@login_required
def inbox_bulk_dismiss(request):
    """Dismiss many rows at once. Expects a POST body with repeated
    `keys` values shaped 'source_type:source_id' (form-encoded, one per
    checked row). Silently skips invalid pairs so a partially-bad batch
    still succeeds on the good rows."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)
    raw_keys = request.POST.getlist('keys')
    from apps.core.models import InboxUserState
    dismissed = 0
    for raw in raw_keys:
        try:
            st, _, sid = raw.partition(':')
            st = (st or '').strip().lower()
            if st not in _VALID_SOURCES or not sid.isdigit():
                continue
            _upsert_inbox_state(request.user, st, sid, is_dismissed=True)
            dismissed += 1
        except Exception:
            continue
    return JsonResponse({'ok': True, 'dismissed': dismissed})


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