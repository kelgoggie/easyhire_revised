from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.core.hashids import encode as _hashid
from apps.employers.models import Company, VerificationDocument


def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('/admin-panel/')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)

        if user is None or not user.is_staff:
            return render(request, 'admin_panel/login.html', {
                'error': 'Invalid credentials or insufficient permissions.',
                'email': email,
            })

        login(request, user)
        return redirect('/admin-panel/')

    return render(request, 'admin_panel/login.html')


def admin_logout(request):
    logout(request)
    return redirect('/admin-panel/login/')


def staff_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect('/admin-panel/login/')
        return view_func(request, *args, **kwargs)
    return wrapper


def _relative(dt):
    """Compact relative time (e.g. '5m ago', '2h ago', 'Mar 4')."""
    from django.utils import timezone
    s = int((timezone.now() - dt).total_seconds())
    if s < 60:     return f"{max(s, 1)}s ago"
    if s < 3600:   return f"{s // 60}m ago"
    if s < 86400:  return f"{s // 3600}h ago"
    if s < 604800: return f"{s // 86400}d ago"
    return dt.strftime("%b %d")


def _resolve_active_nav(path):
    """Pick the sidebar item to highlight based on the current URL path.

    Path matching is prefix-based so detail pages (e.g.
    /admin-panel/companies/<id>/) still highlight 'Companies'. Order
    matters — list longer prefixes first so 'jobs' wins before 'companies'.
    Views can still override by passing their own ``active_nav`` after
    calling _admin_context().
    """
    # (path_prefix, sidebar_key) — first match wins.
    mapping = [
        ('/admin-panel/jobs/',          'jobs'),
        ('/admin-panel/jobseekers/',    'jobseekers'),
        ('/admin-panel/companies/',     'companies'),
        ('/admin-panel/employers/',     'companies'),  # legacy verify path
        ('/admin-panel/reports/',       'reports'),
        ('/admin-panel/announcements/', 'announcements'),
        ('/admin-panel/activity/',      'activity'),
        ('/admin-panel/import/',        'import'),
        ('/admin-panel/settings/',      'settings'),
        ('/admin-panel/change-requests/', 'jobseekers'),
        ('/analytics/',                 'analytics'),
        ('/help/',                      'help'),
        ('/admin-panel/',               'dashboard'),
    ]
    for prefix, key in mapping:
        if path.startswith(prefix):
            return key
    return ''


def _admin_context(request):
    """Shared context for every admin page — sidebar counts + notification feed.

    Notifications fire on three things (per spec):
      1. Pending company verification
      2. Pending personal-info change requests
      3. New user reports
    """
    from apps.employers.models import Company
    from apps.jobseekers.models import PersonalInfoChangeRequest
    from .models import UserReport

    pending_companies = Company.objects.filter(verification_status=Company.PENDING).count()
    pending_jobseekers = PersonalInfoChangeRequest.objects.filter(
        status=PersonalInfoChangeRequest.STATUS_PENDING).count()
    open_reports = UserReport.objects.filter(status=UserReport.STATUS_OPEN).count()

    feed = []
    for c in Company.objects.filter(verification_status=Company.PENDING).order_by('-created_at')[:5]:
        feed.append({
            'icon': 'company',
            'actor': c.name,
            'verb':  'is awaiting partnership approval.',
            'when':  _relative(c.created_at),
            'url':   f'/admin-panel/employers/{_hashid(c.id)}/',
            'at':    c.created_at,
        })
    for r in (PersonalInfoChangeRequest.objects
              .filter(status=PersonalInfoChangeRequest.STATUS_PENDING)
              .select_related('profile').order_by('-submitted_at')[:5]):
        feed.append({
            'icon': 'user',
            'actor': f'{r.profile.first_name} {r.profile.last_name}',
            'verb':  'requested a change of personal information.',
            'when':  _relative(r.submitted_at),
            'url':   f'/admin-panel/jobseekers/{_hashid(r.profile.id)}/',
            'at':    r.submitted_at,
        })
    for ur in (UserReport.objects.filter(status=UserReport.STATUS_OPEN)
               .order_by('-created_at')[:5]):
        # Trim description for inline display; full text is on the reports page.
        reason = (ur.description or '').strip()
        reason_short = reason if len(reason) <= 120 else reason[:117] + '…'
        feed.append({
            'icon': 'flag',
            'actor': ur.filed_by_label,
            'verb':  f'filed a report against {ur.account_label}.',
            'quoted': reason_short,
            'when':  _relative(ur.created_at),
            # Open the Reports page filtered to this row's status so the
            # admin lands on it directly (the page auto-opens the Review
            # modal for ?focus=<id>).
            'url':   f'/admin-panel/reports/?status=open&focus={_hashid(ur.id)}',
            'at':    ur.created_at,
        })
    feed.sort(key=lambda x: x['at'], reverse=True)

    return {
        'pending_companies':     pending_companies,
        'pending_jobseekers':    pending_jobseekers,
        'open_reports':          open_reports,
        'admin_notifications':   feed[:10],
        'admin_attention_count': pending_companies + pending_jobseekers + open_reports,
        # Auto-derived from URL so child templates don't have to thread it
        # explicitly. Views that need a different highlight (e.g.
        # company_job_detail's came_from_jobs flip) overwrite this in
        # their ctx.update(...) after calling _admin_context.
        'active_nav':            _resolve_active_nav(request.path),
    }


@staff_required
def dashboard(request):
    from apps.accounts.models import User
    from apps.jobs.models import JobPosting
    from .models import UserReport
    from apps.matching.engine import (
        WEIGHT_SKILLS, WEIGHT_EDUCATION, WEIGHT_EXPERIENCE, WEIGHT_CERTIFICATIONS,
    )

    pending_approvals = (
        Company.objects.filter(verification_status=Company.PENDING)
        .prefetch_related('verification_docs')
        .order_by('-created_at')[:5]
    )
    recent_reports = (
        UserReport.objects.filter(status=UserReport.STATUS_OPEN)
        .select_related('reported_jobseeker', 'reported_company', 'filed_by')
        .order_by('-created_at')[:5]
    )

    ctx = _admin_context(request)
    ctx.update({
        'total_users':       User.objects.count(),
        'jobseeker_count':   User.objects.filter(user_type=User.JOBSEEKER).count(),
        'employer_count':    User.objects.filter(user_type=User.EMPLOYER).count(),
        'job_count':         JobPosting.objects.count(),
        'pending_approvals': pending_approvals,
        'recent_reports':    recent_reports,
        'algorithm_weights': {
            'skills':         round(WEIGHT_SKILLS * 100),
            'education':      round(WEIGHT_EDUCATION * 100),
            'experience':     round(WEIGHT_EXPERIENCE * 100),
            'certifications': round(WEIGHT_CERTIFICATIONS * 100),
        },
    })
    return render(request, 'admin_panel/dashboard.html', ctx)


@staff_required
def employer_list(request):
    status = request.GET.get('status', 'pending')
    companies = Company.objects.filter(verification_status=status).order_by('-created_at')
    return render(request, 'admin_panel/employer_list.html', {
        'companies': companies,
        'current_status': status,
        'pending_count': Company.objects.filter(verification_status=Company.PENDING).count(),
    })


@staff_required
def employer_detail(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    documents = VerificationDocument.objects.filter(company=company)
    uploaded_types = {doc.doc_type for doc in documents}

    required_docs = [
        VerificationDocument.MAYORS_PERMIT,
        VerificationDocument.PHILJOBNET_ACCREDITATION,
        VerificationDocument.PHILJOBNET_DASHBOARD,
        VerificationDocument.JOB_VACANCIES_LIST,
    ]
    if company.type_of_company in ['local', 'overseas']:
        required_docs += [
            VerificationDocument.PEA_LICENSE,
            VerificationDocument.DO174_CERTIFICATE,
        ]
    if company.type_of_company == 'overseas':
        required_docs += [
            VerificationDocument.POEA_LICENSE,
            VerificationDocument.JOB_ORDER,
        ]

    doc_labels = dict(VerificationDocument.DOC_TYPE_CHOICES)
    checklist = [
        {
            'type': doc_type,
            'label': doc_labels[doc_type],
            'uploaded': doc_type in uploaded_types,
            'doc': next((d for d in documents if d.doc_type == doc_type), None),
        }
        for doc_type in required_docs
    ]

    profile = company.representatives.first()

    ctx = _admin_context(request)
    ctx.update({
        'company':   company,
        'profile':   profile,
        'checklist': checklist,
    })
    return render(request, 'admin_panel/employer_detail.html', ctx)


@staff_required
def set_verification(request, company_id):
    if request.method != 'POST':
        return redirect('admin_panel:employer_detail', company_id=company_id)

    company = get_object_or_404(Company, id=company_id)
    new_status = request.POST.get('status')
    rejection_note = request.POST.get('rejection_note', '').strip()

    valid_statuses = [Company.UNVERIFIED, Company.PENDING, Company.DENIED, Company.VERIFIED]
    if new_status not in valid_statuses:
        return redirect('admin_panel:employer_detail', company_id=company_id)

    prior_status = company.verification_status
    company.verification_status = new_status
    company.rejection_note = rejection_note if new_status == Company.DENIED else ''

    if new_status == Company.VERIFIED:
        company.verified_at = timezone.now()
        company.verified_by = request.user
    else:
        company.verified_at = None
        company.verified_by = None

    company.save()

    # Drop an inbox notice for the company's reps when the status actually
    # changes — verified / denied are the meaningful transitions.
    if new_status != prior_status and new_status in (Company.VERIFIED, Company.DENIED):
        _notify_company_reps_of_verification(company, new_status, rejection_note)

    return redirect('admin_panel:employer_detail', company_id=company_id)


def _notify_company_reps_of_verification(company, new_status, rejection_note):
    """Surface verify/deny outcomes in the employer's EasyHire inbox via an
    AdminAnnouncement targeted at the rep's user account. We piggy-back on
    the announcement audience model because the existing inbox view already
    renders announcements; no new model needed."""
    from .models import AdminAnnouncement
    from apps.employers.models import EmployerProfile

    if new_status == Company.VERIFIED:
        subject = f'Account verified — {company.name}'
        body = (
            f"PESO Iloilo City approved your account for {company.name}.\n\n"
            "You can now post jobs, contact candidates, and invite jobseekers to apply. "
            "Your verification documents are now locked in your Account Verification page; "
            "if PESO ever needs an updated set we'll reopen it for you."
        )
    else:  # DENIED
        reason = rejection_note.strip() if rejection_note else 'No reason provided.'
        subject = f'Account verification denied — {company.name}'
        body = (
            f"PESO Iloilo City reviewed your verification for {company.name} and could not approve it.\n\n"
            f"Reason: {reason}\n\n"
            "Please re-upload the requested documents in your Account Verification page. "
            "Saving any new file resubmits your application automatically."
        )

    # AdminAnnouncement is a broadcast model — use a per-rep notification
    # instead. The Notification model handles it.
    from apps.notifications.models import Notification
    reps = EmployerProfile.objects.filter(company=company).select_related('user')
    for rep in reps:
        if rep.user:
            Notification.objects.create(
                recipient=rep.user,
                notif_type=Notification.EMPLOYER_CONTACTED,  # closest existing bucket
                company=company,
                liker_preview='an account verification update',
                admin_message=f'{subject}\n\n{body}',
            )


# ── Phase 2: Jobseekers ─────────────────────────────────────────────

@staff_required
def jobseeker_list(request):
    from django.core.paginator import Paginator
    from django.db.models import Q
    from apps.jobseekers.models import JobseekerProfile

    search = (request.GET.get('q') or '').strip()
    sort   = (request.GET.get('sort') or 'newest').strip()

    qs = JobseekerProfile.objects.select_related('user').prefetch_related('sectors')
    if search:
        qs = qs.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)  |
            Q(user__email__icontains=search)
        )
    if sort == 'oldest':       qs = qs.order_by('created_at')
    elif sort == 'name_az':    qs = qs.order_by('first_name', 'last_name')
    elif sort == 'name_za':    qs = qs.order_by('-first_name', '-last_name')
    else:                      qs = qs.order_by('-created_at')   # 'newest'

    from apps.core.pagination import querystring_without
    paginator = Paginator(qs, 24)
    page = paginator.get_page(request.GET.get('page') or 1)

    ctx = _admin_context(request)
    ctx.update({
        'page':    page,
        'search':  search,
        'sort':    sort,
        'qs_base': querystring_without(request, 'page'),
    })
    return render(request, 'admin_panel/jobseeker_list.html', ctx)


def _surrounding_jobseeker_ids(pk):
    """Return (prev_id, next_id) for the detail-page pagination, ordered by id."""
    from apps.jobseekers.models import JobseekerProfile
    ids = list(JobseekerProfile.objects.order_by('id').values_list('id', flat=True))
    try:
        idx = ids.index(pk)
    except ValueError:
        return None, None
    prev_id = ids[idx - 1] if idx > 0 else None
    next_id = ids[idx + 1] if idx + 1 < len(ids) else None
    return prev_id, next_id


@staff_required
def jobseeker_detail(request, pk):
    from apps.jobseekers.models import (
        JobseekerProfile, Education, Skill, Certification, WorkExperience,
    )
    from apps.core.pagination import paginate, querystring_without

    jobseeker = get_object_or_404(JobseekerProfile.objects.select_related('user'), pk=pk)
    educations    = Education.objects.filter(profile=jobseeker).order_by('-year_started')
    skills        = Skill.objects.filter(profile=jobseeker)
    certifications = Certification.objects.filter(profile=jobseeker)
    experiences   = WorkExperience.objects.filter(profile=jobseeker).order_by('-year_started', '-id')

    from apps.jobs.models import Application, JobPosting
    applications = (Application.objects.filter(jobseeker=jobseeker)
                    .select_related('job', 'job__company')
                    .order_by('-created_at')[:10])

    prev_id, next_id = _surrounding_jobseeker_ids(pk)

    from apps.jobseekers.models import PersonalInfoChangeRequest
    pending_change = (PersonalInfoChangeRequest.objects
                      .filter(profile=jobseeker, status=PersonalInfoChangeRequest.STATUS_PENDING)
                      .order_by('-submitted_at').first())

    # Top compatible jobs across the platform (excludes jobs they already applied to).
    ranked_jobs = []
    if jobseeker.profile_complete:
        from apps.matching.engine import compute_match_score
        already_applied = set(
            Application.objects.filter(jobseeker=jobseeker).values_list('job_id', flat=True)
        )
        scored = []
        for job in (JobPosting.objects
                    .filter(status=JobPosting.STATUS_OPEN)
                    .exclude(id__in=already_applied)
                    .select_related('company', 'experience_requirement')
                    .prefetch_related('skill_requirements', 'education_requirements')):
            try:
                s = compute_match_score(job, jobseeker)
                scored.append({'job': job, 'score': s.get('total', 0)})
            except Exception:
                continue
        scored.sort(key=lambda x: -x['score'])
        ranked_jobs = scored

    jobs_page = paginate(request, ranked_jobs, per_page=8, page_param='jobs_page')

    ctx = _admin_context(request)
    ctx.update({
        'jobseeker':      jobseeker,
        'educations':     educations,
        'skills':         skills,
        'certifications': certifications,
        'experiences':    experiences,
        'applications':   applications,
        'prev_id':        prev_id,
        'next_id':        next_id,
        'pending_change': pending_change,
        'jobs_page':           jobs_page,
        'jobs_ranked':         list(jobs_page.object_list),
        'jobs_qs_base':        querystring_without(request, 'jobs_page'),
    })
    return render(request, 'admin_panel/jobseeker_detail.html', ctx)


@staff_required
def jobseeker_settings(request, pk):
    from apps.jobseekers.models import JobseekerProfile
    from datetime import datetime
    from .models import AuditLog

    jobseeker = get_object_or_404(JobseekerProfile.objects.select_related('user'), pk=pk)
    saved_section = None
    error = None

    if request.method == 'POST':
        form = (request.POST.get('form') or '').strip()

        if form == 'personal':
            jobseeker.first_name  = request.POST.get('first_name', jobseeker.first_name).strip()
            jobseeker.middle_name = request.POST.get('middle_name', '').strip()
            jobseeker.last_name   = request.POST.get('last_name', jobseeker.last_name).strip()
            jobseeker.suffix      = request.POST.get('suffix', '').strip()
            sex = request.POST.get('sex', '').strip()
            if sex in {'M', 'F'}:
                jobseeker.sex = sex
            dob_raw = request.POST.get('date_of_birth', '').strip()
            if dob_raw:
                for fmt in ('%m/%d/%Y', '%B %d, %Y'):
                    try:
                        jobseeker.date_of_birth = datetime.strptime(dob_raw, fmt).date()
                        break
                    except ValueError:
                        continue
            jobseeker.save()
            AuditLog.objects.create(
                admin=request.user, action=AuditLog.ACTION_EDIT,
                target_model='JobseekerProfile', target_id=jobseeker.id,
                notes='Edited personal information.',
            )
            saved_section = 'personal'

        elif form == 'password':
            new1 = request.POST.get('new_password', '')
            new2 = request.POST.get('confirm_password', '')
            if len(new1) < 8:
                error = 'New password must be at least 8 characters.'
            elif new1 != new2:
                error = "Passwords don't match."
            else:
                jobseeker.user.set_password(new1)
                jobseeker.user.save(update_fields=['password'])
                AuditLog.objects.create(
                    admin=request.user, action=AuditLog.ACTION_RESET_PASSWORD,
                    target_model='User', target_id=jobseeker.user.id,
                    notes='Admin reset password.',
                )
                saved_section = 'password'

        elif form == 'disable':
            jobseeker.user.is_active = False
            jobseeker.user.save(update_fields=['is_active'])
            AuditLog.objects.create(
                admin=request.user, action=AuditLog.ACTION_DEACTIVATE,
                target_model='User', target_id=jobseeker.user.id,
                notes='Admin disabled account.',
            )
            saved_section = 'disabled'

        elif form == 'enable':
            jobseeker.user.is_active = True
            jobseeker.user.save(update_fields=['is_active'])
            AuditLog.objects.create(
                admin=request.user, action=AuditLog.ACTION_REACTIVATE,
                target_model='User', target_id=jobseeker.user.id,
                notes='Admin re-enabled account.',
            )
            saved_section = 'enabled'

    ctx = _admin_context(request)
    ctx.update({
        'jobseeker':     jobseeker,
        'saved_section': saved_section,
        'error':         error,
    })
    return render(request, 'admin_panel/jobseeker_settings.html', ctx)


@staff_required
def jobseeker_application_detail(request, pk, app_id):
    from apps.jobseekers.models import (
        JobseekerProfile, Education, Skill, Certification, WorkExperience,
    )
    from apps.jobs.models import Application
    from apps.matching.engine import compute_match_score

    jobseeker = get_object_or_404(JobseekerProfile.objects.select_related('user'), pk=pk)
    app = get_object_or_404(
        Application.objects.select_related('job', 'job__company'),
        id=app_id, jobseeker=jobseeker,
    )
    job = app.job

    score_data = compute_match_score(job, jobseeker) if jobseeker.profile_complete else {
        'total': 0, 'breakdown': {}
    }

    educations    = Education.objects.filter(profile=jobseeker).order_by('-year_started')
    skills        = Skill.objects.filter(profile=jobseeker)
    certifications = Certification.objects.filter(profile=jobseeker)
    experiences   = WorkExperience.objects.filter(profile=jobseeker).order_by('-year_started', '-id')

    # Prev / next other applications for THIS jobseeker
    app_ids = list(Application.objects.filter(jobseeker=jobseeker)
                   .order_by('-created_at').values_list('id', flat=True))
    try:
        idx = app_ids.index(app.id)
    except ValueError:
        idx = -1
    prev_app_id = app_ids[idx - 1] if idx > 0 else None
    next_app_id = app_ids[idx + 1] if 0 <= idx < len(app_ids) - 1 else None

    ctx = _admin_context(request)
    ctx.update({
        'jobseeker':     jobseeker,
        'app':           app,
        'job':           job,
        'score':         score_data.get('total', 0),
        'breakdown':     score_data.get('breakdown', {}),
        'educations':    educations,
        'skills':        skills,
        'certifications': certifications,
        'experiences':   experiences,
        'prev_app_id':   prev_app_id,
        'next_app_id':   next_app_id,
    })
    return render(request, 'admin_panel/jobseeker_application_detail.html', ctx)


# ── Phase 3: Companies ─────────────────────────────────────────────

# Reason choices for admin job-deletion. Used by the modal + persisted to notification.
JOB_DELETION_REASONS = [
    ('duplicate',     'Duplicate posting'),
    ('spam',          'Spam or low-quality post'),
    ('misleading',    'Misleading or inaccurate'),
    ('inappropriate', 'Inappropriate content'),
    ('discrimination','Discriminatory language'),
    ('outdated',      'Outdated / no longer relevant'),
    ('fraud',         'Suspected fraudulent posting'),
    ('policy',        'Violates platform policy'),
    ('other',         'Other (see admin notes)'),
]


@staff_required
def company_list(request):
    from django.core.paginator import Paginator
    from django.db.models import Q
    search = (request.GET.get('q') or '').strip()
    sort   = (request.GET.get('sort') or 'newest').strip()

    qs = Company.objects.all()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(company_email__icontains=search))
    if sort == 'oldest':     qs = qs.order_by('created_at')
    elif sort == 'name_az':  qs = qs.order_by('name')
    elif sort == 'name_za':  qs = qs.order_by('-name')
    else:                    qs = qs.order_by('-created_at')

    from apps.core.pagination import querystring_without
    paginator = Paginator(qs, 24)
    page = paginator.get_page(request.GET.get('page') or 1)

    ctx = _admin_context(request)
    ctx.update({'page': page, 'search': search, 'sort': sort,
                'qs_base': querystring_without(request, 'page')})
    return render(request, 'admin_panel/company_list.html', ctx)


def _surrounding_company_ids(pk):
    ids = list(Company.objects.order_by('id').values_list('id', flat=True))
    try:
        idx = ids.index(pk)
    except ValueError:
        return None, None
    prev_id = ids[idx - 1] if idx > 0 else None
    next_id = ids[idx + 1] if idx + 1 < len(ids) else None
    return prev_id, next_id


@staff_required
def company_detail(request, pk):
    from apps.jobs.models import JobPosting, Application
    from django.db.models import Count, Q as DjQ

    company = get_object_or_404(
        Company.objects.prefetch_related('verification_docs', 'sector_badges'), pk=pk,
    )
    jobs = (
        JobPosting.objects.filter(company=company)
        .annotate(
            applicants_count=Count('applications', distinct=True),
            hired_count=Count(
                'applications',
                filter=DjQ(applications__status=Application.STATUS_HIRED),
                distinct=True,
            ),
        )
        .select_related('experience_requirement')
        .prefetch_related('skill_requirements', 'certification_requirements', 'education_requirements')
        .order_by('-created_at')
    )
    rep = company.representatives.first()
    prev_id, next_id = _surrounding_company_ids(pk)

    ctx = _admin_context(request)
    ctx.update({
        'company':      company,
        'rep':          rep,
        'jobs':         jobs,
        'prev_id':      prev_id,
        'next_id':      next_id,
        'reasons':      JOB_DELETION_REASONS,
    })
    return render(request, 'admin_panel/company_detail.html', ctx)


@staff_required
def company_settings(request, pk):
    from .models import AuditLog
    company = get_object_or_404(Company, pk=pk)
    rep = company.representatives.first()
    saved_section = None
    error = None

    if request.method == 'POST':
        form = (request.POST.get('form') or '').strip()

        if form == 'company':
            company.name              = request.POST.get('name', company.name).strip()
            company.company_email     = request.POST.get('company_email', company.company_email).strip()
            company.recruitment_email = request.POST.get('recruitment_email', company.recruitment_email).strip()
            company.main_branch_address = request.POST.get('main_branch_address', company.main_branch_address).strip()
            company.description       = request.POST.get('description', '').strip()
            company.save()
            AuditLog.objects.create(
                admin=request.user, action=AuditLog.ACTION_EDIT,
                target_model='Company', target_id=company.id,
                notes='Edited company information.',
            )
            saved_section = 'company'

        elif form == 'password' and rep:
            new1 = request.POST.get('new_password', '')
            new2 = request.POST.get('confirm_password', '')
            if len(new1) < 8:
                error = 'New password must be at least 8 characters.'
            elif new1 != new2:
                error = "Passwords don't match."
            else:
                rep.user.set_password(new1)
                rep.user.save(update_fields=['password'])
                AuditLog.objects.create(
                    admin=request.user, action=AuditLog.ACTION_RESET_PASSWORD,
                    target_model='User', target_id=rep.user.id,
                    notes='Admin reset password for company representative.',
                )
                saved_section = 'password'

        elif form == 'disable' and rep:
            rep.user.is_active = False
            rep.user.save(update_fields=['is_active'])
            AuditLog.objects.create(
                admin=request.user, action=AuditLog.ACTION_DEACTIVATE,
                target_model='User', target_id=rep.user.id,
                notes='Admin disabled company representative account.',
            )
            saved_section = 'disabled'

        elif form == 'enable' and rep:
            rep.user.is_active = True
            rep.user.save(update_fields=['is_active'])
            AuditLog.objects.create(
                admin=request.user, action=AuditLog.ACTION_REACTIVATE,
                target_model='User', target_id=rep.user.id,
                notes='Admin re-enabled company representative account.',
            )
            saved_section = 'enabled'

        elif form == 'verification':
            # Inline verification status change so admins can update without
            # bouncing to the dedicated verify page. Mirrors set_verification.
            new_status     = (request.POST.get('verification_status') or '').strip()
            rejection_note = (request.POST.get('rejection_note') or '').strip()
            valid = {Company.UNVERIFIED, Company.PENDING, Company.DENIED, Company.VERIFIED}
            if new_status not in valid:
                error = 'Pick a valid verification status.'
            else:
                prior = company.verification_status
                company.verification_status = new_status
                company.rejection_note = rejection_note if new_status == Company.DENIED else ''
                if new_status == Company.VERIFIED:
                    company.verified_at = timezone.now()
                    company.verified_by = request.user
                else:
                    company.verified_at = None
                    company.verified_by = None
                company.save()
                # Notify reps when the outcome flips to verified or denied —
                # piggy-backs on the verification-notification helper.
                if new_status != prior and new_status in (Company.VERIFIED, Company.DENIED):
                    _notify_company_reps_of_verification(company, new_status, rejection_note)
                AuditLog.objects.create(
                    admin=request.user, action=AuditLog.ACTION_EDIT,
                    target_model='Company', target_id=company.id,
                    notes=f'Set verification status to {new_status}.'
                          + (f' Reason: {rejection_note}' if rejection_note else ''),
                )
                saved_section = 'verification'

    # Verification documents context — same shape pending.html uses so the
    # checklist renders identically here.
    from apps.employers.models import VerificationDocument
    required_docs = [
        VerificationDocument.MAYORS_PERMIT,
        VerificationDocument.PHILJOBNET_ACCREDITATION,
        VerificationDocument.PHILJOBNET_DASHBOARD,
        VerificationDocument.JOB_VACANCIES_LIST,
    ]
    if company.type_of_company in ['local', 'overseas']:
        required_docs += [VerificationDocument.PEA_LICENSE,
                          VerificationDocument.DO174_CERTIFICATE]
    if company.type_of_company == 'overseas':
        required_docs += [VerificationDocument.POEA_LICENSE,
                          VerificationDocument.JOB_ORDER]
    uploaded = {
        doc.doc_type: doc
        for doc in VerificationDocument.objects.filter(company=company)
    }
    doc_labels = dict(VerificationDocument.DOC_TYPE_CHOICES)
    checklist = [
        {
            'type':     doc_type,
            'label':    doc_labels[doc_type],
            'uploaded': doc_type in uploaded,
            'doc':      uploaded.get(doc_type),
        }
        for doc_type in required_docs
    ]

    ctx = _admin_context(request)
    ctx.update({
        'company':         company,
        'rep':             rep,
        'saved_section':   saved_section,
        'error':           error,
        'checklist':       checklist,
        'uploaded_count':  sum(1 for item in checklist if item['uploaded']),
        # Status-picker options for the verification form.
        'verification_choices': Company.VERIFICATION_CHOICES,
    })
    return render(request, 'admin_panel/company_settings.html', ctx)


@staff_required
def job_match_detail(request, pk, job_id, jobseeker_id):
    """Admin view of a jobseeker in the context of a specific job match.
    Mirrors jobseeker_application_detail but works for non-applicants too —
    used when admin clicks a Top Match on the company job detail page.
    """
    from apps.jobseekers.models import (
        JobseekerProfile, Education, Skill, Certification, WorkExperience,
    )
    from apps.jobs.models import JobPosting, Application
    from apps.matching.engine import compute_match_score, get_ranked_jobseekers

    company = get_object_or_404(Company, pk=pk)
    job = get_object_or_404(JobPosting, pk=job_id, company=company)
    jobseeker = get_object_or_404(JobseekerProfile.objects.select_related('user'), pk=jobseeker_id)

    score_data = compute_match_score(job, jobseeker) if jobseeker.profile_complete else {
        'total': 0, 'breakdown': {}
    }

    educations    = Education.objects.filter(profile=jobseeker).order_by('-year_started')
    skills        = Skill.objects.filter(profile=jobseeker)
    certifications = Certification.objects.filter(profile=jobseeker)
    experiences   = WorkExperience.objects.filter(profile=jobseeker).order_by('-year_started', '-id')

    # Prev/Next walks the ranked non-applicant jobseekers for this job.
    applicant_ids = set(Application.objects.filter(job=job).values_list('jobseeker_id', flat=True))
    ranked_ids = [r['profile'].id for r in get_ranked_jobseekers(job) if r['profile'].id not in applicant_ids]
    prev_id = next_id = None
    try:
        idx = ranked_ids.index(jobseeker.id)
        if idx > 0:
            prev_id = ranked_ids[idx - 1]
        if idx < len(ranked_ids) - 1:
            next_id = ranked_ids[idx + 1]
    except ValueError:
        pass

    # Whether they actually applied (for the small status hint at the top).
    application = Application.objects.filter(jobseeker=jobseeker, job=job).first()

    ctx = _admin_context(request)
    ctx.update({
        'active_nav':    'companies',
        'company':       company,
        'job':           job,
        'jobseeker':     jobseeker,
        'application':   application,
        'score':         score_data.get('total', 0),
        'breakdown':     score_data.get('breakdown', {}),
        'educations':    educations,
        'skills':        skills,
        'certifications': certifications,
        'experiences':   experiences,
        'prev_id':       prev_id,
        'next_id':       next_id,
    })
    return render(request, 'admin_panel/job_match_detail.html', ctx)


@staff_required
def company_job_detail(request, pk, job_id):
    """Admin read-only view of a company job post + top-ranked jobseekers."""
    from apps.jobs.models import JobPosting, Application
    from apps.matching.engine import get_ranked_jobseekers
    from apps.core.pagination import paginate, querystring_without

    company = get_object_or_404(Company, pk=pk)
    job = get_object_or_404(JobPosting.objects.select_related('company'), pk=job_id, company=company)

    # Applications for this job — surfaced as a dedicated "Applicants" section
    # the admin can jump to via #applicants anchor from the count in the header.
    from apps.matching.engine import compute_match_score
    apps_qs = (Application.objects.filter(job=job)
               .select_related('jobseeker', 'jobseeker__user')
               .order_by('-created_at'))
    applicants = []
    for app in apps_qs:
        try:
            score = compute_match_score(job, app.jobseeker)['total']
        except Exception:
            score = None
        applicants.append({
            'app':   app,
            'score': score,
        })

    # Matches across all jobseekers (excluding people who already applied),
    # then paginate eight per page.
    applicant_ids = {a['app'].jobseeker_id for a in applicants}
    ranked = [r for r in get_ranked_jobseekers(job) if r['profile'].id not in applicant_ids]
    matches_page = paginate(request, ranked, per_page=8, page_param='matches_page')

    # Did the user land here from the global Jobs page? The link adds
    # ?from=jobs so we can highlight Jobs in the sidebar instead of
    # Companies, and flip the back-link target to /admin-panel/jobs/.
    came_from_jobs = request.GET.get('from') == 'jobs'

    ctx = _admin_context(request)
    ctx.update({
        'active_nav':       'jobs' if came_from_jobs else 'companies',
        'came_from_jobs':   came_from_jobs,
        'company':          company,
        'job':              job,
        'ranked':           list(matches_page.object_list),
        'matches_page':     matches_page,
        'matches_qs_base':  querystring_without(request, 'matches_page'),
        'applicants':       applicants,
        'applicants_count': len(applicants),
        # Reason choices for the Delete modal (the take-down endpoint
        # company_delete_job expects one of these codes).
        'reasons':          JOB_DELETION_REASONS,
    })
    return render(request, 'admin_panel/company_job_detail.html', ctx)


@staff_required
def company_delete_job(request, pk, job_id):
    """Delete a job posting and notify the company with the admin's reason."""
    from django.http import JsonResponse
    from apps.jobs.models import JobPosting
    from apps.notifications.models import Notification
    from .models import AuditLog

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)

    company = get_object_or_404(Company, pk=pk)
    job = get_object_or_404(JobPosting, pk=job_id, company=company)

    reason_code = (request.POST.get('reason') or '').strip()
    reason_dict = dict(JOB_DELETION_REASONS)
    if reason_code not in reason_dict:
        return JsonResponse({'ok': False, 'error': 'Pick a deletion reason.'}, status=400)
    reason_label = reason_dict[reason_code]
    admin_notes  = (request.POST.get('notes') or '').strip()

    # Snapshot what we need before deletion.
    job_title = job.title

    # Notify every representative of the company.
    full_message = f"Reason: {reason_label}"
    if admin_notes:
        full_message += f". Admin notes: {admin_notes}"
    for rep in company.representatives.all():
        Notification.objects.create(
            recipient=rep.user,
            notif_type=Notification.JOB_DELETED_BY_ADMIN,
            company=company,
            liker_preview=job_title[:200],
            admin_message=full_message[:1000],
        )

    AuditLog.objects.create(
        admin=request.user, action=AuditLog.ACTION_DELETE,
        target_model='JobPosting', target_id=job.id,
        notes=f"Deleted job '{job_title}'. {full_message}",
    )

    job.delete()
    return JsonResponse({'ok': True, 'message': f'Deleted "{job_title}".'})


# ── User report submission (jobseeker reports a company, employer reports a jobseeker) ─

REPORT_REASONS = {
    'inappropriate_language': 'Inappropriate language',
    'misleading':             'Misleading information',
    'discrimination':         'Discriminatory content',
    'spam':                   'Spam or low-quality content',
    'fraud':                  'Suspected fraud or scam',
    'harassment':             'Harassment',
    'other':                  'Other',
}


@login_required
def report_submit(request):
    """POST /api/report/  — file a UserReport about a jobseeker or a company.

    Body params:
      target_type: 'jobseeker' | 'employer'
      target_id:   pk of the JobseekerProfile or Company being reported
      reason:      one of REPORT_REASONS keys
      other_text:  optional, used when reason='other', clipped to 100 chars
    """
    from django.http import JsonResponse
    from .models import UserReport

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)

    target_type = (request.POST.get('target_type') or '').strip()
    target_id   = (request.POST.get('target_id') or '').strip()
    reason_code = (request.POST.get('reason') or '').strip()
    other_text  = (request.POST.get('other_text') or '').strip()[:100]

    if reason_code not in REPORT_REASONS:
        return JsonResponse({'ok': False, 'error': 'Pick a reason.'}, status=400)
    if reason_code == 'other' and not other_text:
        return JsonResponse({'ok': False, 'error': 'Please describe the reason.'}, status=400)

    label = REPORT_REASONS[reason_code]
    description = f'Other: {other_text}' if reason_code == 'other' else label
    if reason_code != 'other' and other_text:
        description = f'{label} — {other_text}'

    if target_type == 'jobseeker':
        from apps.jobseekers.models import JobseekerProfile
        target = get_object_or_404(JobseekerProfile, id=target_id)
        # Disallow self-reports.
        if request.user.is_jobseeker:
            try:
                if request.user.jobseeker_profile.id == target.id:
                    return JsonResponse({'ok': False, 'error': "You can't report yourself."}, status=400)
            except Exception:
                pass
        UserReport.objects.create(
            reported_jobseeker=target, account_type=UserReport.ACCOUNT_JOBSEEKER,
            description=description, filed_by=request.user,
        )
    elif target_type == 'employer':
        from apps.employers.models import Company
        target = get_object_or_404(Company, id=target_id)
        if request.user.is_employer:
            try:
                if request.user.employer_profile.company_id == target.id:
                    return JsonResponse({'ok': False, 'error': "You can't report your own company."}, status=400)
            except Exception:
                pass
        UserReport.objects.create(
            reported_company=target, account_type=UserReport.ACCOUNT_EMPLOYER,
            description=description, filed_by=request.user,
        )
    else:
        return JsonResponse({'ok': False, 'error': 'Invalid target.'}, status=400)

    return JsonResponse({'ok': True})



@staff_required
def algorithm_settings(request):
    from .models import SiteSettings, AuditLog
    settings = SiteSettings.get()
    saved_form = None   # 'weights' | 'site' on success — drives the success modal + active tab
    error = None
    active_tab = request.GET.get('tab', 'algorithm')

    if request.method == 'POST':
        form_name = request.POST.get('form_name', 'weights')

        if form_name == 'weights':
            active_tab = 'algorithm'
            try:
                sk = int(request.POST.get('weight_skills', 0))
                ed = int(request.POST.get('weight_education', 0))
                ex = int(request.POST.get('weight_experience', 0))
                ce = int(request.POST.get('weight_certifications', 0))
            except (TypeError, ValueError):
                error = 'Weights must be whole numbers.'
                sk = ed = ex = ce = 0

            if error is None:
                if any(v < 0 or v > 100 for v in (sk, ed, ex, ce)):
                    error = 'Each weight must be between 0 and 100.'
                elif (sk + ed + ex + ce) != 100:
                    error = f"Weights must add up to 100% (currently {sk + ed + ex + ce}%)."
                else:
                    settings.weight_skills         = sk / 100.0
                    settings.weight_education      = ed / 100.0
                    settings.weight_experience     = ex / 100.0
                    settings.weight_certifications = ce / 100.0
                    settings.updated_by = request.user
                    settings.save(update_fields=[
                        'weight_skills', 'weight_education', 'weight_experience',
                        'weight_certifications', 'updated_by', 'updated_at',
                    ])
                    AuditLog.objects.create(
                        admin=request.user, action=AuditLog.ACTION_EDIT,
                        target_model='SiteSettings', target_id=settings.id,
                        notes=f'Updated matching weights to S{sk}/E{ed}/X{ex}/C{ce}.',
                    )
                    saved_form = 'weights'

        elif form_name == 'site':
            active_tab = 'site'
            office  = (request.POST.get('office_address') or '').strip()[:255]
            email   = (request.POST.get('contact_email') or '').strip()[:254]
            hotline = (request.POST.get('hotline') or '').strip()[:40]
            try:
                htf_days       = int(request.POST.get('hard_to_fill_days', settings.hard_to_fill_days))
                htf_threshold  = int(request.POST.get('hard_to_fill_applicant_threshold', settings.hard_to_fill_applicant_threshold))
                compat_thresh  = float(request.POST.get('compatibility_threshold', settings.compatibility_threshold))
            except (TypeError, ValueError):
                error = 'Numeric fields must be valid numbers.'
                htf_days = htf_threshold = 0
                compat_thresh = 0.0

            if error is None:
                if htf_days < 1 or htf_threshold < 0 or not (0 <= compat_thresh <= 100):
                    error = 'Numeric fields are out of allowed range.'
                else:
                    settings.office_address = office
                    settings.contact_email  = email
                    settings.hotline        = hotline
                    settings.hard_to_fill_days = htf_days
                    settings.hard_to_fill_applicant_threshold = htf_threshold
                    settings.compatibility_threshold = compat_thresh
                    settings.updated_by = request.user
                    settings.save(update_fields=[
                        'office_address', 'contact_email', 'hotline',
                        'hard_to_fill_days', 'hard_to_fill_applicant_threshold',
                        'compatibility_threshold', 'updated_by', 'updated_at',
                    ])
                    AuditLog.objects.create(
                        admin=request.user, action=AuditLog.ACTION_EDIT,
                        target_model='SiteSettings', target_id=settings.id,
                        notes='Updated site settings (contact info / thresholds).',
                    )
                    saved_form = 'site'

    ctx = _admin_context(request)
    ctx.update({
        'settings': settings,
        'weight_skills_pct':         round(settings.weight_skills * 100),
        'weight_education_pct':      round(settings.weight_education * 100),
        'weight_experience_pct':     round(settings.weight_experience * 100),
        'weight_certifications_pct': round(settings.weight_certifications * 100),
        'active_tab':  active_tab,
        'saved_form':  saved_form,
        'error':       error,
    })
    return render(request, 'admin_panel/algorithm_settings.html', ctx)


# ── Phase 4: Reports admin ──────────────────────────────────────────

@staff_required
def report_list(request):
    from django.core.paginator import Paginator
    from django.db.models import Q
    from .models import UserReport

    search = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or 'open').strip()

    qs = UserReport.objects.select_related(
        'reported_jobseeker', 'reported_company', 'filed_by'
    ).order_by('-created_at')
    if status in {'open', 'reviewed', 'dismissed'}:
        qs = qs.filter(status=status)
    elif status == 'all':
        pass
    else:
        qs = qs.filter(status='open')

    if search:
        qs = qs.filter(
            Q(description__icontains=search) |
            Q(reported_jobseeker__first_name__icontains=search) |
            Q(reported_jobseeker__last_name__icontains=search)  |
            Q(reported_company__name__icontains=search)         |
            Q(filed_by__email__icontains=search)
        )

    from apps.core.pagination import querystring_without
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page') or 1)

    ctx = _admin_context(request)
    ctx.update({'page': page, 'search': search, 'status': status,
                'qs_base': querystring_without(request, 'page')})
    return render(request, 'admin_panel/report_list.html', ctx)


@staff_required
def report_review(request, report_id):
    """POST mark a report as reviewed or dismissed."""
    from django.http import JsonResponse
    from django.utils import timezone
    from .models import UserReport, AuditLog

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)

    report = get_object_or_404(UserReport, id=report_id)
    decision = (request.POST.get('decision') or '').strip()
    if decision not in {'reviewed', 'dismissed'}:
        return JsonResponse({'ok': False, 'error': 'Pick a decision.'}, status=400)

    report.status = decision
    report.reviewed_at = timezone.now()
    report.save(update_fields=['status', 'reviewed_at'])
    AuditLog.objects.create(
        admin=request.user, action=AuditLog.ACTION_EDIT,
        target_model='UserReport', target_id=report.id,
        notes=f'Marked report as {decision}.',
    )
    return JsonResponse({'ok': True, 'status': report.status})


# ── Phase 5: Personal-info change-request review ────────────────────

@staff_required
def change_request_review(request, request_id):
    """POST decision=approve|reject for a PersonalInfoChangeRequest.

    On approve: copy requested values onto the JobseekerProfile.
    On reject : leave the profile alone; the user just sees the request go away.
    Both paths stamp reviewed_at + write an AuditLog entry.
    """
    from django.http import JsonResponse
    from django.utils import timezone
    from apps.jobseekers.models import PersonalInfoChangeRequest
    from .models import AuditLog

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)

    req = get_object_or_404(PersonalInfoChangeRequest, id=request_id)
    decision = (request.POST.get('decision') or '').strip()
    if decision not in {'approve', 'reject'}:
        return JsonResponse({'ok': False, 'error': 'Pick a decision.'}, status=400)
    if req.status != PersonalInfoChangeRequest.STATUS_PENDING:
        return JsonResponse({
            'ok': False, 'error': f"Request is already '{req.get_status_display()}'.",
        }, status=409)

    if decision == 'approve':
        profile = req.profile
        profile.first_name  = req.first_name
        profile.middle_name = req.middle_name
        profile.last_name   = req.last_name
        profile.suffix      = req.suffix
        if req.date_of_birth:
            profile.date_of_birth = req.date_of_birth
        if req.sex:
            profile.sex = req.sex
        profile.save()
        req.status = PersonalInfoChangeRequest.STATUS_APPROVED
    else:
        req.status = PersonalInfoChangeRequest.STATUS_REJECTED

    req.reviewed_at = timezone.now()
    req.save(update_fields=['status', 'reviewed_at'])

    AuditLog.objects.create(
        admin=request.user, action=AuditLog.ACTION_EDIT,
        target_model='PersonalInfoChangeRequest', target_id=req.id,
        notes=f"{decision.title()}d personal-info change for {req.profile.first_name} {req.profile.last_name}.",
    )

    # Notify the jobseeker.
    from apps.notifications.models import Notification
    from apps.notifications.email import email_personal_info_decision
    Notification.objects.create(
        recipient=req.profile.user,
        notif_type=(Notification.PERSONAL_INFO_APPROVED if decision == 'approve'
                    else Notification.PERSONAL_INFO_REJECTED),
        jobseeker=req.profile,
    )
    email_personal_info_decision(req, approved=(decision == 'approve'))
    return JsonResponse({'ok': True, 'status': req.status})


# ── Activity log viewer ────────────────────────────────────────────

@staff_required
def activity_log(request):
    from django.core.paginator import Paginator
    from django.db.models import Q
    from .models import AuditLog

    search = (request.GET.get('q') or '').strip()
    action = (request.GET.get('action') or '').strip()

    qs = AuditLog.objects.select_related('admin').order_by('-created_at')
    if search:
        qs = qs.filter(
            Q(notes__icontains=search) |
            Q(target_model__icontains=search) |
            Q(admin__email__icontains=search)
        )
    if action:
        qs = qs.filter(action=action)

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page') or 1)

    from apps.core.pagination import querystring_without

    ctx = _admin_context(request)
    ctx.update({
        'page':           page,
        'qs_base':        querystring_without(request, 'page'),
        'search':         search,
        'action':         action,
        'action_choices': AuditLog.ACTION_CHOICES,
    })
    return render(request, 'admin_panel/activity_log.html', ctx)


# ── Bulk import (CSV) ──────────────────────────────────────────────

@staff_required
def bulk_import(request):
    """Sync CSV upload + processing. Suitable for small batches (<1000 rows).
    For larger files, swap the per-row loop for a Celery task later.
    """
    from django.utils import timezone
    from .models import ImportBatch, AuditLog
    import csv, io

    saved_results = None
    error = None

    if request.method == 'POST':
        import_type = request.POST.get('import_type', '').strip()
        upload      = request.FILES.get('file')
        if import_type not in {ImportBatch.IMPORT_JOBSEEKERS, ImportBatch.IMPORT_COMPANIES}:
            error = 'Pick what you are importing.'
        elif not upload:
            error = 'Choose a CSV file to upload.'
        elif upload.size > 5 * 1024 * 1024:
            error = 'File too large (5MB max).'
        else:
            # Read the file's bytes BEFORE saving — saving consumes the pointer.
            raw_bytes = upload.read()
            upload.seek(0)
            batch = ImportBatch.objects.create(
                imported_by=request.user, import_type=import_type,
                file=upload, status=ImportBatch.STATUS_PROCESSING,
            )
            try:
                decoded = raw_bytes.decode('utf-8-sig')
                reader  = list(csv.DictReader(io.StringIO(decoded)))
                batch.total_rows = len(reader)
                ok, fail, errs = _process_import(reader, import_type)
                batch.successful_imports = ok
                batch.failed_imports     = fail
                batch.error_log          = errs[:200]   # cap log
                batch.status             = ImportBatch.STATUS_COMPLETE
                batch.completed_at       = timezone.now()
                batch.save()
                AuditLog.objects.create(
                    admin=request.user, action=AuditLog.ACTION_IMPORT,
                    target_model='ImportBatch', target_id=batch.id,
                    notes=f'Imported {ok} {import_type} ({fail} failed) from {upload.name}.',
                )
                saved_results = {
                    'total': batch.total_rows, 'ok': ok, 'fail': fail,
                    'errors': errs[:20], 'type': import_type,
                }
            except Exception as exc:
                batch.status = ImportBatch.STATUS_FAILED
                batch.error_log = [{'row': 0, 'error': str(exc)}]
                batch.save()
                error = f'Import failed: {exc}'

    recent_batches = ImportBatch.objects.select_related('imported_by').order_by('-created_at')[:10]

    ctx = _admin_context(request)
    ctx.update({
        'saved_results': saved_results,
        'error':         error,
        'recent_batches': recent_batches,
    })
    return render(request, 'admin_panel/bulk_import.html', ctx)


# ── Announcements ──────────────────────────────────────────────────

@staff_required
def announcements(request):
    """Compose + browse broadcast announcements from PESO admin to users.
    The audience radio buttons control who sees it in their inbox: all users,
    jobseekers only, or employers only.
    """
    from .models import AdminAnnouncement, AuditLog
    from apps.core.pagination import paginate, querystring_without

    error = None
    saved = False

    if request.method == 'POST':
        audience = (request.POST.get('audience') or '').strip()
        subject  = (request.POST.get('subject') or '').strip()
        body     = (request.POST.get('body') or '').strip()
        valid_audiences = {
            AdminAnnouncement.AUDIENCE_ALL,
            AdminAnnouncement.AUDIENCE_JOBSEEKERS,
            AdminAnnouncement.AUDIENCE_EMPLOYERS,
        }
        if audience not in valid_audiences:
            error = 'Pick an audience.'
        elif not subject:
            error = 'Subject is required.'
        elif not body:
            error = 'Body is required.'
        else:
            ann = AdminAnnouncement.objects.create(
                sender=request.user, audience=audience, subject=subject, body=body,
            )
            AuditLog.objects.create(
                admin=request.user, action=AuditLog.ACTION_EDIT,
                target_model='AdminAnnouncement', target_id=ann.id,
                notes=f'Sent announcement to {ann.get_audience_display()}: {subject[:80]}',
            )
            saved = True

    recent = AdminAnnouncement.objects.select_related('sender').all()
    page = paginate(request, recent, per_page=10)

    ctx = _admin_context(request)
    ctx.update({
        'active_nav': 'announcements',
        'error': error,
        'saved': saved,
        'recent_announcements': list(page.object_list),
        'page': page,
        'qs_base': querystring_without(request, 'page'),
        'audience_choices': AdminAnnouncement.AUDIENCE_CHOICES,
    })
    return render(request, 'admin_panel/announcements.html', ctx)


def _process_import(rows, import_type):
    """Per-row import. Returns (success_count, failure_count, error_list)."""
    from apps.accounts.models import User
    ok, fail, errs = 0, 0, []
    if import_type == 'jobseekers':
        from apps.jobseekers.models import JobseekerProfile
        for i, row in enumerate(rows, start=2):  # row 1 is the header
            try:
                email = (row.get('email') or '').strip().lower()
                if not email:
                    raise ValueError('Missing email')
                if User.objects.filter(email=email).exists():
                    raise ValueError(f'User with email {email} already exists')
                user = User.objects.create_user(
                    email=email, user_type='jobseeker', is_active=True,
                    is_imported=True, is_claimed=False,
                )
                JobseekerProfile.objects.create(
                    user=user,
                    first_name=(row.get('first_name') or '').strip() or '(unknown)',
                    middle_name=(row.get('middle_name') or '').strip(),
                    last_name=(row.get('last_name') or '').strip() or '(unknown)',
                    sex=(row.get('sex') or 'M').strip().upper()[:1] if (row.get('sex') or '').strip().upper()[:1] in {'M', 'F'} else 'M',
                    street_barangay=(row.get('street_barangay') or row.get('address') or '').strip(),
                    phone=(row.get('phone') or '').strip(),
                    contact_email=email,
                )
                ok += 1
            except Exception as exc:
                fail += 1
                errs.append({'row': i, 'error': str(exc)})
    else:  # companies
        from apps.employers.models import Company
        from django.utils.text import slugify
        for i, row in enumerate(rows, start=2):
            try:
                name = (row.get('name') or '').strip()
                if not name:
                    raise ValueError('Missing name')
                base_slug = slugify(name)[:280] or 'company'
                slug = base_slug
                n = 1
                while Company.objects.filter(slug=slug).exists():
                    n += 1
                    slug = f'{base_slug}-{n}'
                Company.objects.create(
                    name=name, slug=slug,
                    type_of_company=(row.get('type_of_company') or 'local').strip(),
                    nature_of_company=(row.get('nature_of_company') or '').strip(),
                    company_email=(row.get('company_email') or '').strip(),
                    recruitment_email=(row.get('recruitment_email') or row.get('company_email') or '').strip(),
                    main_branch_address=(row.get('main_branch_address') or row.get('address') or '').strip(),
                )
                ok += 1
            except Exception as exc:
                fail += 1
                errs.append({'row': i, 'error': str(exc)})
    return ok, fail, errs


# ── Admin: edit a jobseeker's resume ───────────────────────────────

@staff_required
def admin_edit_resume(request, pk):
    """Slimmer resume editor for admins. Same model writes as the jobseeker's
    own resume page, but framed in neutral pronouns ('the jobseeker') and
    targeting any profile by id.
    """
    from apps.jobseekers.models import (
        JobseekerProfile, Education, Skill, Certification, WorkExperience,
    )
    from .models import AuditLog

    jobseeker = get_object_or_404(JobseekerProfile.objects.select_related('user'), pk=pk)
    saved = False

    if request.method == 'POST':
        # Bio
        jobseeker.bio = (request.POST.get('bio') or '').strip()
        jobseeker.save(update_fields=['bio'])

        # Wipe-and-recreate the four list-style sections (same pattern the
        # jobseeker view uses) — kept simple to mirror that flow.
        Education.objects.filter(profile=jobseeker).delete()
        for level, course, inst, ystart, yend, current in zip(
            request.POST.getlist('edu_level'),
            request.POST.getlist('edu_course'),
            request.POST.getlist('edu_institution'),
            request.POST.getlist('edu_start'),
            request.POST.getlist('edu_end'),
            [str(i) for i in range(len(request.POST.getlist('edu_level')))],
        ):
            if level or course or inst:
                Education.objects.create(
                    profile=jobseeker,
                    level=(level or '').strip(),
                    course_degree=(course or '').strip(),
                    institution=(inst or '').strip(),
                    year_started=int(ystart) if (ystart or '').isdigit() else None,
                    year_ended=int(yend) if (yend or '').isdigit() else None,
                )

        Skill.objects.filter(profile=jobseeker).delete()
        for name in request.POST.getlist('skill_name'):
            n = (name or '').strip()
            if n:
                Skill.objects.create(profile=jobseeker, name=n)

        Certification.objects.filter(profile=jobseeker).delete()
        for cname, corg in zip(
            request.POST.getlist('cert_name'),
            request.POST.getlist('cert_org'),
        ):
            if (cname or '').strip():
                Certification.objects.create(
                    profile=jobseeker,
                    name=(cname or '').strip(),
                    issuing_org=(corg or '').strip(),
                )

        # Work experience
        WorkExperience.objects.filter(profile=jobseeker).delete()
        positions    = request.POST.getlist('exp_position')
        companies    = request.POST.getlist('exp_company')
        descs        = request.POST.getlist('exp_description')
        starts       = request.POST.getlist('exp_start_month_year')
        ends         = request.POST.getlist('exp_end_month_year')
        currents_idx = set(request.POST.getlist('exp_is_current'))
        for i, pos in enumerate(positions):
            if not (pos or '').strip():
                continue
            def _split(v):
                if v and '-' in v:
                    parts = v.split('-')
                    return parts[1].lstrip('0') or '0', parts[0]
                return '', None
            s_month, s_year = _split(starts[i] if i < len(starts) else '')
            e_month, e_year = _split(ends[i]   if i < len(ends)   else '')
            is_current = str(i) in currents_idx
            WorkExperience.objects.create(
                profile=jobseeker,
                position=(pos or '').strip(),
                company=(companies[i] if i < len(companies) else '').strip(),
                description=(descs[i] if i < len(descs) else '').strip(),
                month_started=s_month, year_started=int(s_year) if s_year else None,
                month_ended=e_month if not is_current else '',
                year_ended=int(e_year) if e_year and not is_current else None,
                is_current=is_current,
            )

        AuditLog.objects.create(
            admin=request.user, action=AuditLog.ACTION_EDIT,
            target_model='JobseekerProfile', target_id=jobseeker.id,
            notes='Admin edited resume.',
        )
        saved = True

    educations     = Education.objects.filter(profile=jobseeker).order_by('-year_started')
    skills         = Skill.objects.filter(profile=jobseeker)
    certifications = Certification.objects.filter(profile=jobseeker)
    experiences    = WorkExperience.objects.filter(profile=jobseeker).order_by('-year_started', '-id')

    from apps.jobseekers.models import Education as Edu
    edu_levels = Edu.LEVELS

    ctx = _admin_context(request)
    ctx.update({
        'jobseeker':      jobseeker,
        'educations':     educations,
        'skills':         skills,
        'certifications': certifications,
        'experiences':    experiences,
        'edu_levels':     edu_levels,
        'year_range':     range(1980, 2031),
        'saved':          saved,
    })


# ── Admin: global jobs index + take-down actions ─────────────────────

@staff_required
def admin_jobs_list(request):
    """Global jobs index. Search across title + company name, filter by
    status, sort by newest/oldest/most-applicants."""
    from apps.jobs.models import JobPosting
    from django.db.models import Count, Q

    search = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip()
    sort   = (request.GET.get('sort') or 'newest').strip()

    qs = (JobPosting.objects
          .select_related('company')
          .annotate(applicants_count=Count('applications', distinct=True)))

    if search:
        qs = qs.filter(Q(title__icontains=search) |
                       Q(company__name__icontains=search))

    if status in {'open', 'closed', 'draft', 'admin_disabled'}:
        if status == 'admin_disabled':
            qs = qs.filter(admin_disabled=True)
        elif status == 'closed':
            # Distinguish voluntary close from admin take-down.
            qs = qs.filter(status='closed', admin_disabled=False)
        else:
            qs = qs.filter(status=status)

    if sort == 'oldest':
        qs = qs.order_by('created_at')
    elif sort == 'applicants':
        qs = qs.order_by('-applicants_count', '-created_at')
    else:  # newest
        qs = qs.order_by('-created_at')

    # Per-status counts for the filter chips (count over the search-filtered
    # queryset so totals stay meaningful as you search).
    base_for_counts = JobPosting.objects.all()
    if search:
        base_for_counts = base_for_counts.filter(
            Q(title__icontains=search) | Q(company__name__icontains=search)
        )
    status_counts = {
        'all':            base_for_counts.count(),
        'open':           base_for_counts.filter(status='open').count(),
        'closed':         base_for_counts.filter(status='closed', admin_disabled=False).count(),
        'draft':          base_for_counts.filter(status='draft').count(),
        'admin_disabled': base_for_counts.filter(admin_disabled=True).count(),
    }

    from django.core.paginator import Paginator
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page', 1))

    ctx = _admin_context(request)
    ctx.update({
        'active_nav':    'jobs',
        'page':          page,
        'search':        search,
        'status':        status,
        'sort':          sort,
        'status_counts': status_counts,
    })
    return render(request, 'admin_panel/jobs_list.html', ctx)


@staff_required
def admin_job_disable(request, job_id):
    """Take a job down. Marks ``admin_disabled=True`` + closes it + notifies
    every company rep with the admin-supplied reason."""
    from apps.jobs.models import JobPosting
    from apps.notifications.models import Notification
    from .models import AuditLog
    from apps.employers.models import EmployerProfile

    job = get_object_or_404(JobPosting.objects.select_related('company'), id=job_id)
    if request.method != 'POST':
        return redirect('admin_panel:company_job_detail', pk=job.company_id, job_id=job_id)

    reason = (request.POST.get('reason') or '').strip()
    if not reason:
        return JsonResponse({'ok': False, 'error': 'Reason is required.'}, status=400)

    job.admin_disabled = True
    job.admin_disabled_reason = reason
    job.status = 'closed'
    job.save(update_fields=['admin_disabled', 'admin_disabled_reason', 'status'])

    # Notify every rep of the company with the reason.
    for rep in EmployerProfile.objects.filter(company=job.company).select_related('user'):
        if rep.user:
            Notification.objects.create(
                recipient=rep.user,
                notif_type=Notification.JOB_DELETED_BY_ADMIN,
                company=job.company,
                job=job,
                liker_preview=job.title,    # snapshot for the bell text
                admin_message=reason,
            )

    AuditLog.objects.create(
        admin=request.user, action=AuditLog.ACTION_EDIT,
        target_model='JobPosting', target_id=job.id,
        notes=f'Disabled job "{job.title}". Reason: {reason}',
    )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('admin_panel:company_job_detail', pk=job.company_id, job_id=job_id)


@staff_required
def admin_job_reopen(request, job_id):
    """Lift an admin take-down — clears the flag + reason + flips status
    back to open. POST only."""
    from apps.jobs.models import JobPosting
    from .models import AuditLog

    job = get_object_or_404(JobPosting, id=job_id)
    if request.method != 'POST':
        return redirect('admin_panel:company_job_detail', pk=job.company_id, job_id=job_id)

    job.admin_disabled = False
    job.admin_disabled_reason = ''
    job.status = 'open'
    job.save(update_fields=['admin_disabled', 'admin_disabled_reason', 'status'])

    AuditLog.objects.create(
        admin=request.user, action=AuditLog.ACTION_EDIT,
        target_model='JobPosting', target_id=job.id,
        notes=f'Re-opened admin-disabled job "{job.title}".',
    )
    return redirect('admin_panel:company_job_detail', pk=job.company_id, job_id=job_id)
    return render(request, 'admin_panel/admin_edit_resume.html', ctx)