from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.employers.models import Company, VerificationDocument
from apps.jobseekers.models import JobseekerProfile, Education, Skill, Certification, WorkExperience
from apps.employers.models import CandidateInteraction
from apps.core.hashids import encode as _hashid


def landing(request):
    # The employer marketing page is unused — the navbar CTA and root /employers/
    # both jump straight to sign-in. EmployerLoginView redirects authenticated
    # employers on to their dashboard from there.
    return redirect('/employers/login/')


def employer_required(view_func):
    """Allow any logged-in employer with a profile — verified OR pending.
    Use this for pages that should stay usable while a company waits for verification
    (dashboard, settings, company profile, etc.). The pending banner on the dashboard
    tells the user what's still gated.

    Admins hitting employer-only URLs bounce to the admin panel rather than
    the employer login page — landing them on a sign-in form when they're
    already signed in reads as broken.
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/employers/login/')
        if request.user.is_staff:
            return redirect('/admin-panel/')
        if not request.user.is_employer:
            return redirect('/employers/login/')
        try:
            _ = request.user.employer_profile
        except Exception:
            return redirect('/employers/register/')
        return view_func(request, *args, **kwargs)
    return wrapper


def employer_verified_required(view_func):
    """Stricter gate — require the company to be verified.
    Pending companies hit this and bounce to dashboard with a session flag the
    banner uses to show a 'why was I redirected' note.
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/employers/login/')
        if not request.user.is_employer:
            return redirect('/employers/login/')
        try:
            profile = request.user.employer_profile
        except Exception:
            return redirect('/employers/register/')
        if not profile.company.is_verified:
            request.session['pending_block_msg'] = (
                'This action is unavailable until your company is verified.'
            )
            return redirect('/employers/dashboard/')
        return view_func(request, *args, **kwargs)
    return wrapper


def email_verified_required(view_func):
    """Formerly blocked publishing actions until email was verified. With
    SMTP deferred (see /password-recovery/ and thesis notes), the effective
    identity gate on the employer side is company `verification_status`
    reviewed by PESO admins — a stronger signal than an automated email
    link anyway. This decorator now enforces only auth + is_active.

    Kept as a decorator (rather than removed) so the intent at the call
    site is still readable: "this action is publishing-tier, requires an
    authenticated + active employer".
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/employers/login/')
        if not request.user.is_active:
            return redirect('/employers/login/')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required(login_url='/employers/login/')
def pending(request):
    """Account Verification page — always accessible to employers, with the
    upload UI locked once verified. If PESO sets the company back to
    'pending' or 'verification_denied' later, the page unlocks for re-upload.
    """
    if not request.user.is_employer:
        return redirect('/employers/login/')
    try:
        profile = request.user.employer_profile
        company = profile.company
    except Exception:
        return redirect('/employers/register/')

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

    uploaded = {
        doc.doc_type: doc
        for doc in VerificationDocument.objects.filter(company=company)
    }
    doc_labels = dict(VerificationDocument.DOC_TYPE_CHOICES)
    checklist = [
        {
            'type': doc_type,
            'label': doc_labels[doc_type],
            'uploaded': doc_type in uploaded,
            'doc': uploaded.get(doc_type),
        }
        for doc_type in required_docs
    ]
    uploaded_count = sum(1 for item in checklist if item['uploaded'])

    # Drain flashes: upload rejection (size limit / incomplete set) + the
    # one-shot "documents submitted" confirmation after a successful
    # submit_verification() call.
    upload_error_msg = request.session.pop('upload_error_msg', None)
    verification_submitted_msg = request.session.pop('verification_submitted_msg', None)

    return render(request, 'employers/pending.html', {
        'company': company,
        'profile': profile,
        'checklist': checklist,
        'uploaded_count': uploaded_count,
        'all_uploaded': uploaded_count == len(checklist),
        # Lock the upload UI once verified — only PESO bumping the status
        # back to pending/denied re-opens it for the employer.
        'locked': company.verification_status == Company.VERIFIED,
        'upload_error_msg': upload_error_msg,
        'verification_submitted_msg': verification_submitted_msg,
    })


@login_required(login_url='/employers/login/')
def company_logo_upload(request):
    """POST an image to replace the company logo. Mirrors the jobseeker
    profile_picture_upload pattern (5 MB cap, delete-then-attach)."""
    from django.http import JsonResponse
    if request.method != 'POST' or not request.user.is_employer:
        return JsonResponse({'ok': False, 'error': 'Bad request'}, status=400)
    try:
        company = request.user.employer_profile.company
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Company not found'}, status=404)

    image = request.FILES.get('image')
    if not image:
        return JsonResponse({'ok': False, 'error': 'No image provided'}, status=400)
    if image.size > 5 * 1024 * 1024:
        return JsonResponse({'ok': False, 'error': 'Image must be under 5 MB'}, status=400)

    if company.logo:
        company.logo.delete(save=False)
    company.logo = image
    company.save(update_fields=['logo', 'updated_at'])
    return JsonResponse({'ok': True, 'url': company.logo.url})


@login_required(login_url='/employers/login/')
def company_logo_remove(request):
    """POST to clear the company logo — restores the placeholder icon."""
    from django.http import JsonResponse
    if request.method != 'POST' or not request.user.is_employer:
        return JsonResponse({'ok': False, 'error': 'Bad request'}, status=400)
    try:
        company = request.user.employer_profile.company
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Company not found'}, status=404)
    if company.logo:
        company.logo.delete(save=False)
        company.logo = None
        company.save(update_fields=['logo', 'updated_at'])
    return JsonResponse({'ok': True})


@login_required(login_url='/employers/login/')
def upload_document(request):
    if request.method != 'POST':
        return redirect('/employers/pending/')
    try:
        company = request.user.employer_profile.company
    except Exception:
        return redirect('/employers/register/')

    # PESO already approved this company — uploads are locked from the UI but
    # also enforced here in case someone POSTs directly.
    if company.verification_status == Company.VERIFIED:
        return redirect('/employers/pending/')

    # 10 MB limit — matches the "Max 10 MB per file" copy on pending.html.
    # Kept generous because scanned Mayor's Permits and multi-page PDFs
    # legitimately land in the 3–8 MB range.
    MAX_UPLOAD_BYTES = 10 * 1024 * 1024

    doc_type = request.POST.get('doc_type')
    file = request.FILES.get('file')
    if doc_type and file:
        if file.size > MAX_UPLOAD_BYTES:
            # Human-readable size for the flash. Uses MB with one decimal.
            size_mb = file.size / (1024 * 1024)
            request.session['upload_error_msg'] = (
                f'"{file.name}" is {size_mb:.1f} MB — larger than the 10 MB '
                f'per-file limit. Compress the file or split into smaller pages '
                f'and try again.'
            )
            return redirect('/employers/pending/')

        VerificationDocument.objects.filter(company=company, doc_type=doc_type).delete()
        VerificationDocument.objects.create(company=company, doc_type=doc_type, file=file)
        # Uploads no longer auto-forward to PESO — the employer now hits an
        # explicit "Submit for Verification" button on pending.html so they
        # can review the set first. See submit_verification() below.

    return redirect('/employers/pending/')


@login_required(login_url='/employers/login/')
def submit_verification(request):
    """Explicit push into the PESO review queue.

    Flips UNVERIFIED / DENIED → PENDING. Requires all required documents to
    be in place so employers can't accidentally submit a half-complete set.
    """
    if request.method != 'POST':
        return redirect('/employers/pending/')
    try:
        company = request.user.employer_profile.company
    except Exception:
        return redirect('/employers/register/')

    # Nothing to do if already PENDING or VERIFIED — the submit button won't
    # be rendered in those states either, but guard against POSTing anyway.
    if company.verification_status not in (Company.UNVERIFIED, Company.DENIED):
        return redirect('/employers/pending/')

    # Match pending() view's required_docs derivation so we don't submit a
    # short set. Duplicated for lookup safety — pending() already has this
    # exact list.
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

    uploaded_types = set(
        VerificationDocument.objects
        .filter(company=company)
        .values_list('doc_type', flat=True)
    )
    if not all(dt in uploaded_types for dt in required_docs):
        request.session['upload_error_msg'] = (
            'Upload every required document before submitting for verification.'
        )
        return redirect('/employers/pending/')

    company.verification_status = Company.PENDING
    company.rejection_note = ''
    company.save(update_fields=['verification_status', 'rejection_note'])
    request.session['verification_submitted_msg'] = (
        'Documents submitted. PESO Iloilo City will review your application '
        'within 1–3 business days.'
    )
    return redirect('/employers/pending/')


@employer_required
def dashboard(request):
    profile = request.user.employer_profile
    company = profile.company
    from apps.jobs.models import JobPosting
    from django.db.models import Count

    recent_jobs = (
        JobPosting.objects.filter(company=company)
        .annotate(applicants_count=Count('applications'))
        .order_by('-created_at')[:5]
    )

    # Drain any "you can't do that yet" message from a verified-required redirect.
    pending_block_msg = request.session.pop('pending_block_msg', None)

    return render(request, 'employers/dashboard.html', {
        'profile': profile,
        'company': company,
        'recent_jobs': recent_jobs,
        'pending_block_msg': pending_block_msg,
        'unread_notifications': False,
        'unread_messages': False,
    })


from apps.jobs.models import (
    JobPosting, JobEducationRequirement,
    JobSkillRequirement, JobCertificationRequirement,
    JobExperienceRequirement
)


@employer_required
def job_list(request):
    from apps.jobseekers.models import JobInteraction
    from django.db.models import Count, Q
    profile = request.user.employer_profile
    company = profile.company
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    sort = request.GET.get('sort', 'newest')

    base = JobPosting.objects.filter(company=company).annotate(
        liked_by_count=Count(
            'jobseeker_interactions',
            filter=Q(jobseeker_interactions__interaction_type='liked')
        ),
        applicants_count=Count('applications', distinct=True),
    ).select_related('experience_requirement'
    ).prefetch_related('skill_requirements', 'certification_requirements', 'education_requirements')

    if query:
        base = base.filter(title__icontains=query)

    # Non-deleted queryset drives the All/Open/Closed pills. Deleted rows
    # get their own tab + count and never mix into the other buckets.
    live = base.filter(deleted_at__isnull=True)
    all_count     = live.count()
    open_count    = live.filter(status=JobPosting.STATUS_OPEN).count()
    closed_count  = live.filter(status=JobPosting.STATUS_CLOSED).count()
    deleted_count = base.filter(deleted_at__isnull=False).count()

    if status_filter == 'open':
        jobs = live.filter(status=JobPosting.STATUS_OPEN)
    elif status_filter == 'closed':
        jobs = live.filter(status=JobPosting.STATUS_CLOSED)
    elif status_filter == 'deleted':
        jobs = base.filter(deleted_at__isnull=False)
    else:
        jobs = live
        status_filter = ''  # normalize any junk value back to "All"

    if sort == 'oldest':
        jobs = jobs.order_by('created_at')
    elif sort == 'most_liked':
        jobs = jobs.order_by('-liked_by_count')
    else:
        jobs = jobs.order_by('-created_at')

    return render(request, 'employers/job_list.html', {
        'company': company,
        'jobs': jobs,
        'query': query,
        'status_filter': status_filter,
        'sort': sort,
        'all_count':     all_count,
        'open_count':    open_count,
        'closed_count':  closed_count,
        'deleted_count': deleted_count,
        'unread_notifications': False,
        'unread_messages': False,
    })

@employer_verified_required
@email_verified_required
def job_create(request):
    profile = request.user.employer_profile
    company = profile.company

    if request.method == 'POST':
        # Core job
        vis = (request.POST.get('visibility') or '').strip()
        if vis not in {JobPosting.VISIBILITY_PUBLIC, JobPosting.VISIBILITY_MEMBERS}:
            vis = JobPosting.VISIBILITY_PUBLIC
        job = JobPosting.objects.create(
            company=company,
            title=request.POST.get('title', ''),
            description=request.POST.get('description', ''),
            location_type=request.POST.get('location_type', 'iloilo'),
            bldg_unit=request.POST.get('bldg_unit', ''),
            street=request.POST.get('street', ''),
            barangay_code=request.POST.get('job_barangay', ''),
            barangay_name=request.POST.get('job_barangay_name', ''),
            overseas_address=request.POST.get('overseas_address', ''),
            slots=request.POST.get('slots') or 1,
            salary_min=request.POST.get('salary_min') or None,
            salary_max=request.POST.get('salary_max') or None,
            status=request.POST.get('status', 'open'),
            visibility=vis,
        )

        # Education requirements (may be multiple)
        edu_levels  = request.POST.getlist('edu_level')
        edu_courses = request.POST.getlist('edu_course')
        for i, level in enumerate(edu_levels):
            if level:
                JobEducationRequirement.objects.create(
                    job=job,
                    level=level,
                    course_degree=edu_courses[i] if i < len(edu_courses) else '',
                )

        # Skills
        for name in request.POST.getlist('skill_name'):
            if name.strip():
                JobSkillRequirement.objects.create(
                    job=job,
                    name=name.strip(),
                    is_required=True,
                )

        # Certifications
        cert_names = request.POST.getlist('cert_name')
        cert_orgs = request.POST.getlist('cert_org')
        for i, name in enumerate(cert_names):
            if name.strip():
                JobCertificationRequirement.objects.create(
                    job=job,
                    name=name.strip(),
                    issuing_org=cert_orgs[i] if i < len(cert_orgs) else '',
                )

        # Experience
        months = request.POST.get('exp_months')
        if months:
            # `exp_preferred_position` is submitted as one hidden input per
            # chip in the typer above the field. Join them into the single
            # comma-separated CharField that JobExperienceRequirement stores.
            positions = [p.strip() for p in request.POST.getlist('exp_preferred_position') if p.strip()]
            JobExperienceRequirement.objects.create(
                job=job,
                months_required=months,
                description=request.POST.get('exp_description', ''),
                any_experience_accepted='any_experience_accepted' in request.POST,
                preferred_position=', '.join(positions),
            )

        # Notify every jobseeker whose match score against this newly-
        # posted job clears 80. Runs synchronously — fine at Iloilo scale
        # (couple thousand seekers max); if it ever starts to add latency
        # a Celery job is the natural swap.
        try:
            from apps.notifications.utils import notify_high_match_jobseekers
            notify_high_match_jobseekers(job, threshold=80)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                'notify_high_match_jobseekers failed for job %s', job.id,
            )

        return redirect('/employers/jobs/')

    # Prefill location with the company's Iloilo branch address as the default.
    # Fallback chain: (1) the company's structured iloilo_* fields captured at
    # registration, (2) the location of the most recent job the company posted
    # (so a repeat poster gets last-time's values pre-filled), (3) the free-text
    # main_branch_address as a street hint (seeded / legacy companies may only
    # have this filled in). All four keys end up as strings, never None.
    last_job = (
        JobPosting.objects.filter(company=company, deleted_at__isnull=True)
        .order_by('-created_at').first()
    )
    location_defaults = {
        'bldg_unit':     company.iloilo_bldg_unit    or (last_job.bldg_unit     if last_job else '') or '',
        'street':        company.iloilo_street       or (last_job.street        if last_job else '') or (company.main_branch_address or ''),
        'barangay_code': company.iloilo_barangay_code or (last_job.barangay_code if last_job else '') or '',
        'barangay_name': company.iloilo_barangay_name or (last_job.barangay_name if last_job else '') or '',
    }
    return render(request, 'employers/job_form.html', {
        'company': company,
        'action': 'Create',
        'job': None,
        'location_defaults': location_defaults,
        # Job creation always runs under the employer chrome; admins don't
        # create jobs for a company, they just moderate existing ones.
        'base_template': 'base/base_dashboard_employer.html',
        'is_admin_edit': False,
        'unread_notifications': False,
        'unread_messages': False,
    })



def job_edit(request, job_id):
    """Edit any job post. Two valid callers:
      - Employer rep editing their company's own job (verified + email-verified).
      - PESO admin editing anybody's job (staff bypass — no email check needed).
    Routed by two URL patterns that both point here; the auth check below
    figures out which flow we're in.
    """
    if not request.user.is_authenticated:
        return redirect('/employers/login/')

    if request.user.is_staff:
        # Admin path — accept any job by id.
        job = get_object_or_404(JobPosting.objects.select_related('company'), id=job_id)
        company = job.company
        is_admin_edit = True
    else:
        # Employer path — strict ownership + verification gates.
        if not request.user.is_employer:
            return redirect('/employers/login/')
        try:
            profile = request.user.employer_profile
        except Exception:
            return redirect('/employers/register/')
        company = profile.company
        if not company.is_verified:
            request.session['pending_block_msg'] = (
                'This action is unavailable until your company is verified.'
            )
            return redirect('/employers/dashboard/')
        # Email-verification gate removed — see email_verified_required
        # docstring above. Company `verification_status` (PESO-reviewed) is
        # the actual identity gate for publishing actions.
        job = get_object_or_404(JobPosting, id=job_id, company=company)
        is_admin_edit = False

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if title:
            job.title = title
        job.description = request.POST.get('description', '')
        job.location_type = request.POST.get('location_type', 'iloilo')
        job.bldg_unit = request.POST.get('bldg_unit', '')
        job.street = request.POST.get('street', '')
        job.barangay_code = request.POST.get('job_barangay', '')
        job.barangay_name = request.POST.get('job_barangay_name', '')
        job.overseas_address = request.POST.get('overseas_address', '')
        job.slots = request.POST.get('slots') or 1
        job.salary_min = request.POST.get('salary_min') or None
        job.salary_max = request.POST.get('salary_max') or None
        job.status = request.POST.get('status', 'open')
        _vis = (request.POST.get('visibility') or '').strip()
        if _vis in {JobPosting.VISIBILITY_PUBLIC, JobPosting.VISIBILITY_MEMBERS}:
            job.visibility = _vis
        job.save()

        # Education (may be multiple)
        JobEducationRequirement.objects.filter(job=job).delete()
        edu_levels  = request.POST.getlist('edu_level')
        edu_courses = request.POST.getlist('edu_course')
        for i, level in enumerate(edu_levels):
            if level:
                JobEducationRequirement.objects.create(
                    job=job,
                    level=level,
                    course_degree=edu_courses[i] if i < len(edu_courses) else '',
                )

        # Skills
        JobSkillRequirement.objects.filter(job=job).delete()
        for name in request.POST.getlist('skill_name'):
            if name.strip():
                JobSkillRequirement.objects.create(job=job, name=name.strip(), is_required=True)

        # Certifications
        JobCertificationRequirement.objects.filter(job=job).delete()
        cert_names = request.POST.getlist('cert_name')
        cert_orgs = request.POST.getlist('cert_org')
        for i, name in enumerate(cert_names):
            if name.strip():
                JobCertificationRequirement.objects.create(
                    job=job,
                    name=name.strip(),
                    issuing_org=cert_orgs[i] if i < len(cert_orgs) else '',
                )

        # Experience
        JobExperienceRequirement.objects.filter(job=job).delete()
        months = request.POST.get('exp_months')
        if months:
            positions = [p.strip() for p in request.POST.getlist('exp_preferred_position') if p.strip()]
            JobExperienceRequirement.objects.create(
                job=job,
                months_required=months,
                description=request.POST.get('exp_description', ''),
                any_experience_accepted='any_experience_accepted' in request.POST,
                preferred_position=', '.join(positions),
            )

        # Admin edits return to the admin job detail; employer edits go to
        # the employer's job list (existing behavior).
        if is_admin_edit:
            from apps.core.hashids import encode as _hashid
            return redirect(f'/admin-panel/companies/{_hashid(company.id)}/jobs/{_hashid(job.id)}/')
        return redirect('/employers/jobs/')

    return render(request, 'employers/job_form.html', {
        'company': company,
        'action': 'Edit',
        'job': job,
        'is_admin_edit': is_admin_edit,
        # Route the template through the admin chrome when a PESO admin is
        # editing — the employer sidebar's tabs (Dashboard / My Job Posts /
        # Analytics / Verification) are nonsensical for an admin who came
        # in from the admin panel.
        'base_template': (
            'admin_panel/base_admin.html' if is_admin_edit
            else 'base/base_dashboard_employer.html'
        ),
        # All edit-mode prefills come from `job.*`; this empty dict just keeps
        # the template's `|default:location_defaults.*` chain from raising.
        'location_defaults': {'bldg_unit': '', 'street': '', 'barangay_code': '', 'barangay_name': ''},
        'unread_notifications': False,
        'unread_messages': False,
    })


@employer_verified_required
def job_delete(request, job_id):
    """Employer-side job delete — soft. Sets deleted_at instead of
    hard-deleting so the job can be restored from the Deleted tab within
    30 days. Admin purge then wipes rows whose deleted_at has aged out.
    Refuses to touch admin-disabled jobs so PESO's take-down record
    (with reason) isn't lost."""
    from django.contrib import messages
    from django.utils import timezone
    profile = request.user.employer_profile
    job = get_object_or_404(JobPosting, id=job_id, company=profile.company)
    if request.method == 'POST':
        if job.admin_disabled:
            messages.error(
                request,
                'This job was disabled by PESO Admin and can\'t be deleted from your side. '
                'Contact PESO to discuss next steps.',
            )
            return redirect('/employers/jobs/')
        if not job.deleted_at:
            job.deleted_at = timezone.now()
            job.save(update_fields=['deleted_at'])
    return redirect('/employers/jobs/?status=deleted')


@employer_verified_required
def job_restore(request, job_id):
    """Undo a soft-delete. Available while the job is still in the 30-day
    trash window. Refuses to restore a PESO-deleted row — those are
    permanent from the employer's side (matches the hidden Restore button
    on job_list.html for admin_deleted=True). A flash tells the employer
    why the click bounced when they hit the URL directly."""
    from django.contrib import messages
    profile = request.user.employer_profile
    job = get_object_or_404(JobPosting, id=job_id, company=profile.company)
    if request.method == 'POST' and job.deleted_at:
        if job.admin_deleted:
            messages.error(
                request,
                'This job was deleted by PESO Admin and cannot be restored. '
                'Check your inbox for the reason.',
            )
        else:
            job.deleted_at = None
            job.save(update_fields=['deleted_at'])
    return redirect('/employers/jobs/?status=deleted')


@employer_verified_required
def job_close(request, job_id):
    """Toggle a job between OPEN and CLOSED. Closed jobs hide from jobseeker
    recommendations and stop receiving new applications, but stay on record.

    Refuses to re-open an admin-disabled job — only PESO can lift their
    own take-down. A flash message tells the employer why their click bounced.
    """
    from django.contrib import messages
    profile = request.user.employer_profile
    job = get_object_or_404(JobPosting, id=job_id, company=profile.company)
    if request.method == 'POST':
        # Block re-open attempts on admin take-downs. Closing is also blocked
        # (already closed) but the bounce message is what matters.
        if job.admin_disabled:
            messages.error(
                request,
                'This job was disabled by PESO Admin and can\'t be re-opened from your side. '
                'Check your inbox for the reason and contact PESO if you have questions.',
            )
        elif job.status == JobPosting.STATUS_OPEN:
            job.status = JobPosting.STATUS_CLOSED
            job.save(update_fields=['status'])
        elif job.status == JobPosting.STATUS_CLOSED:
            job.status = JobPosting.STATUS_OPEN
            job.save(update_fields=['status'])
    return redirect(request.POST.get('next') or '/employers/jobs/')


@employer_verified_required
def job_mark_external_hires(request, job_id):
    """Record how many people were hired for this job outside the platform.

    External hires occupy real slots on the posting — same treatment as
    platform hires (which decrement `slots` in the hire flow). So every
    change here delta-adjusts `slots` alongside `externally_hired_count`:
        delta = new_external - old_external
        slots -= delta   (delta > 0 uses new slots; delta < 0 frees them)

    Rejects any update that would push `slots` below 0. Sends JSON when
    called via AJAX so the modal can update the button label in place;
    falls back to a redirect otherwise.
    """
    from django.http import JsonResponse
    profile = request.user.employer_profile
    job = get_object_or_404(JobPosting, id=job_id, company=profile.company)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method != 'POST':
        return redirect(f'/employers/jobs/{_hashid(job.id)}/')

    raw = (request.POST.get('count') or '').strip()
    try:
        new_count = int(raw)
    except (TypeError, ValueError):
        new_count = -1
    if new_count < 0:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Enter a whole number 0 or greater.'}, status=400)
        return redirect(f'/employers/jobs/{_hashid(job.id)}/')

    old_count = int(job.externally_hired_count or 0)
    remaining_slots = int(job.slots or 0)
    delta = new_count - old_count

    # Overflow guard: can't record more external hires than there are open
    # slots. remaining_slots already reflects the current external count
    # (each prior save decremented slots), so the check is simply
    # `delta <= remaining_slots`.
    if delta > remaining_slots:
        max_allowed = old_count + remaining_slots
        msg = (
            f"Can't record {new_count} external hires — this job only has "
            f"{remaining_slots} slot{'' if remaining_slots == 1 else 's'} left "
            f"(max you can set is {max_allowed}). Reopen a closed slot or "
            f"increase the job's slot count first."
        )
        if is_ajax:
            return JsonResponse({'ok': False, 'error': msg}, status=400)
        return redirect(f'/employers/jobs/{_hashid(job.id)}/')

    job.externally_hired_count = new_count
    job.slots = remaining_slots - delta  # delta may be negative → frees a slot
    job.save(update_fields=['externally_hired_count', 'slots'])

    if is_ajax:
        return JsonResponse({
            'ok': True,
            'count': new_count,
            'slots_remaining': job.slots,
        })
    return redirect(f'/employers/jobs/{_hashid(job.id)}/')


@employer_required
def job_detail(request, job_id):
    from apps.matching.engine import get_ranked_jobseekers, compute_match_score
    from apps.jobs.models import Application
    from apps.employers.models import EmployerContact

    profile = request.user.employer_profile
    company = profile.company
    job = get_object_or_404(JobPosting, id=job_id, company=company)

    # Top ranked jobseekers for this job (excluding people who already applied).
    applicant_ids = set(Application.objects.filter(job=job).values_list('jobseeker_id', flat=True))
    ranked = get_ranked_jobseekers(job)
    ranked = [r for r in ranked if r['profile'].id not in applicant_ids][:8]

    # Actual applicants for THIS job. Newest first, capped at 8 to match
    # the Recommended carousel's card count. Rendered on the job detail
    # page above Recommended so the employer sees who has ACTUALLY applied
    # before who they COULD invite.
    applicants = []
    apps_qs = (Application.objects
               .filter(job=job)
               .select_related('jobseeker', 'jobseeker__user')
               .order_by('-created_at')[:8])
    for app in apps_qs:
        try:
            s = compute_match_score(job, app.jobseeker)
            score_total = s.get('total', 0)
        except Exception:
            score_total = 0
        applicants.append({
            'profile': app.jobseeker,
            'score': score_total,
            'application_id': app.id,
            'application_status': app.status,
        })

    # Jobseekers who have already been invited to apply for this job.
    # Sourced from the INVITED_TO_APPLY notification rows (invite_to_apply
    # was rewritten to be notification-only — no EmployerContact created
    # anymore, so the old EmployerContact-based check silently returned
    # an empty set and the button stayed at "Invite to Apply" forever).
    from apps.notifications.models import Notification
    invited_ids = set(
        Notification.objects.filter(
            notif_type=Notification.INVITED_TO_APPLY,
            company=company, job=job,
        ).values_list('jobseeker_id', flat=True)
    )

    return render(request, 'employers/job_detail.html', {
        'company': company,
        'job': job,
        'ranked': ranked,
        'applicants': applicants,
        'invited_ids': invited_ids,
        'applicants_count': len(applicant_ids),
        'unread_notifications': False,
        'unread_messages': False,
    })


@employer_verified_required
@email_verified_required
def invite_to_apply(request, job_id, jobseeker_id):
    """Lightweight "Invite to Apply" — creates a single bell notification
    with a View Job link for the jobseeker. No EmployerContact row, no
    email — Kelly explicitly wants this to be distinct from Send
    Requirements. Idempotent: won't create a second notification if one
    already exists for this (company, job, jobseeker) tuple.
    """
    from django.http import JsonResponse
    from django.contrib import messages as flash
    from apps.jobseekers.models import JobseekerProfile
    from apps.notifications.models import Notification

    if request.method != 'POST':
        return redirect(f'/employers/jobs/{_hashid(job_id)}/')

    profile = request.user.employer_profile
    company = profile.company
    job = get_object_or_404(JobPosting, id=job_id, company=company)
    jobseeker = get_object_or_404(JobseekerProfile, id=jobseeker_id)

    # Idempotency guard: check whether the same invite notification is
    # already live. Match on (recipient, company, job, type) so re-clicking
    # Invite to Apply on a previously-invited jobseeker is a no-op.
    already = False
    if jobseeker.user:
        already = Notification.objects.filter(
            recipient=jobseeker.user,
            notif_type=Notification.INVITED_TO_APPLY,
            company=company, job=job,
        ).exists()

    if not already and jobseeker.user:
        Notification.objects.create(
            recipient=jobseeker.user,
            notif_type=Notification.INVITED_TO_APPLY,
            company=company, jobseeker=jobseeker, job=job,
            # liker_preview is used elsewhere for grouped nudges — for this
            # single-source notification we leave it blank; the verb text
            # is derived from company + job in notifications/views.py.
            liker_preview=job.title,  # snapshot for post-deletion
        )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'already': already})

    if already:
        flash.info(request, f'{jobseeker.first_name} has already been invited to apply as {job.title}.')
    else:
        flash.success(
            request,
            f'Success! {jobseeker.first_name} {jobseeker.last_name} has received your Invitation to Apply as {job.title}.',
        )
    return redirect(f'/employers/jobs/{_hashid(job_id)}/')


@employer_verified_required
def candidates(request, job_id):
    from apps.matching.engine import get_ranked_jobseekers, compute_match_score
    from apps.jobseekers.models import JobInteraction, JobseekerProfile
    from apps.jobs.models import Application
    profile = request.user.employer_profile
    company = profile.company
    job = get_object_or_404(JobPosting, id=job_id, company=company)
    # 'applicants' = people who submitted Application (default)
    # 'recommended' = matching engine results
    tab = request.GET.get('tab', 'applicants')

    # Sort. Default 'match' (best match first). 'lowest_match' shows weakest
    # matches first — useful when the employer wants to manually triage the
    # bottom of the pile. 'recent' / 'oldest' only apply to the applicants
    # tab (recommended candidates have no application date).
    sort = (request.GET.get('sort') or 'match').strip().lower()
    if sort not in {'match', 'lowest_match', 'recent', 'oldest', 'name_az', 'name_za'}:
        sort = 'match'

    # Minimum match threshold — chip values line up with the tier badges.
    try:
        min_match = int(request.GET.get('min_match') or 0)
    except (TypeError, ValueError):
        min_match = 0
    if min_match not in {0, 70, 80, 90, 98}:
        min_match = 0

    liked_ids = list(CandidateInteraction.objects.filter(
        company=company, job=job
    ).values_list('jobseeker_id', flat=True))

    # Jobseekers this company has already invited to THIS job. Sourced from
    # the shared INVITED_TO_APPLY notification store so the button on this
    # page and the one on job_detail.html's carousel agree on state.
    from apps.notifications.models import Notification
    invited_ids = set(
        Notification.objects.filter(
            notif_type=Notification.INVITED_TO_APPLY,
            company=company, job=job,
        ).values_list('jobseeker_id', flat=True)
    )

    # Counts for tab labels
    applicants_count = Application.objects.filter(job=job).count()
    liked_by_count = JobInteraction.objects.filter(
        job=job, interaction_type=JobInteraction.LIKED
    ).count()

    # Default — only populated when tab=='applicants' below.
    status_filter = ''
    status_counts = {}

    if tab == 'recommended':
        ranked = get_ranked_jobseekers(job)
        # Hide people who already applied so the lists complement each other
        applicant_ids = set(Application.objects.filter(job=job).values_list('jobseeker_id', flat=True))
        ranked = [r for r in ranked if r['profile'].id not in applicant_ids]
        _apply_candidates_sort(ranked, sort)

    else:  # 'applicants' (default)
        apps = (Application.objects.filter(job=job)
                .select_related('jobseeker')
                .order_by('-created_at'))

        # Status filter — `?status=pending|viewed|accepted|hire_pending|rejected|hired`.
        # `all` (or anything unrecognized) shows everything.
        valid_statuses = {Application.STATUS_PENDING, Application.STATUS_VIEWED,
                          Application.STATUS_ACCEPTED, Application.STATUS_HIRE_PENDING,
                          Application.STATUS_REJECTED, Application.STATUS_HIRED}
        status_filter = (request.GET.get('status') or '').lower().strip()
        if status_filter in valid_statuses:
            apps = apps.filter(status=status_filter)

        # Count per status across the whole job — drives the chip badges,
        # independent of the current filter.
        status_counts_qs = (Application.objects.filter(job=job)
                            .values_list('status', flat=True))
        per_status = {s: 0 for s in valid_statuses}
        for s in status_counts_qs:
            if s in per_status:
                per_status[s] += 1
        # Ordered list of (code, label, count) for the template chips.
        status_counts = [
            (Application.STATUS_PENDING,      'Pending',      per_status[Application.STATUS_PENDING]),
            (Application.STATUS_VIEWED,       'Viewed',       per_status[Application.STATUS_VIEWED]),
            (Application.STATUS_ACCEPTED,     'In Progress',  per_status[Application.STATUS_ACCEPTED]),
            (Application.STATUS_HIRE_PENDING, 'Hire Offered', per_status[Application.STATUS_HIRE_PENDING]),
            (Application.STATUS_REJECTED,    'Rejected',     per_status[Application.STATUS_REJECTED]),
            (Application.STATUS_HIRED,       'Hired',        per_status[Application.STATUS_HIRED]),
        ]

        ranked = []
        for app in apps:
            score_data = compute_match_score(job, app.jobseeker)
            ranked.append({
                'profile': app.jobseeker,
                'score': score_data['total'],
                'breakdown': score_data['breakdown'],
                'application_id': app.id,
                'application_status': app.status,
                'application_message': app.message,
                'applied_at': app.created_at,
            })
        _apply_candidates_sort(ranked, sort)

    # Apply the match-score threshold across both tabs.
    if min_match:
        ranked = [r for r in ranked if (r.get('score') or 0) >= min_match]

    # Free-text search across both tabs. Substring match (case-insensitive)
    # on the jobseeker's full name and any listed skill — same fields as
    # the All Candidates page so the mental model is consistent.
    search = (request.GET.get('q') or '').strip()
    if search:
        needle = search.lower()
        from apps.jobseekers.models import Skill
        def _matches(r):
            p = r.get('profile')
            if not p:
                return False
            name = f"{p.first_name or ''} {p.last_name or ''}".strip().lower()
            if needle in name:
                return True
            skills = Skill.objects.filter(profile=p).values_list('name', flat=True)
            return any(needle in (s or '').lower() for s in skills)
        ranked = [r for r in ranked if _matches(r)]

    from apps.core.pagination import paginate, querystring_without
    page = paginate(request, ranked, per_page=12)

    min_match_choices = [
        {'value': 0,  'label': 'Any match'},
        {'value': 98, 'label': 'Perfect'},
        {'value': 90, 'label': 'Great+'},
        {'value': 80, 'label': 'Good+'},
        {'value': 70, 'label': 'Decent+'},
    ]

    return render(request, 'employers/candidates.html', {
        'company': company,
        'job': job,
        'ranked': list(page.object_list),
        'liked_ids': liked_ids,
        'invited_ids': invited_ids,
        'liked_by_count': liked_by_count,
        'applicants_count': applicants_count,
        'tab': tab,
        'sort': sort,
        'status_filter': status_filter,
        'status_counts': status_counts,
        'min_match': min_match,
        'min_match_choices': min_match_choices,
        'search': search,
        'page': page,
        'qs_base': querystring_without(request, 'page'),
        'unread_notifications': False,
        'unread_messages': False,
    })


def _apply_candidates_sort(items, sort):
    """In-place sort of the ranked-candidates list by the active sort key.
    Items are dicts containing at least 'score', 'profile', and (for
    application items) 'applied_at'."""
    if sort == 'lowest_match':
        items.sort(key=lambda x: x.get('score') or 0)
    elif sort == 'recent':
        # Applied-at desc; recommended-tab items have no applied_at so they
        # fall to the bottom in a stable way.
        items.sort(key=lambda x: x.get('applied_at') or 0, reverse=True)
    elif sort == 'oldest':
        items.sort(key=lambda x: x.get('applied_at') or 0)
    elif sort == 'name_az':
        items.sort(key=lambda x: ((x['profile'].first_name or '').lower(),
                                  (x['profile'].last_name or '').lower()))
    elif sort == 'name_za':
        items.sort(key=lambda x: ((x['profile'].first_name or '').lower(),
                                  (x['profile'].last_name or '').lower()),
                   reverse=True)
    else:  # 'match' — best first
        items.sort(key=lambda x: -(x.get('score') or 0))


# Valid transitions enforced server-side. Rejected is terminal.
# Hired stays as status='hired' even after un-hire (un-hire = "employment ended"),
# we just stamp employed_until and end the linked work-experience entry.
#
# Hire flow is two-step: employer 'hire' moves accepted → hire_pending (an
# offer to the jobseeker); the jobseeker then accepts (→ hired) or declines
# (→ back to accepted) via the dedicated `application_confirm_hire` view.
# 'cancel_hire' lets the employer withdraw a pending offer.
_ALLOWED_TRANSITIONS = {
    # action -> set of statuses we'll accept this action from
    'view':        {'pending'},
    'accept':      {'pending', 'viewed'},
    'reject':      {'pending', 'viewed', 'accepted', 'hire_pending'},
    'hire':        {'accepted'},                 # offer the hire — jobseeker must confirm
    'cancel_hire': {'hire_pending'},             # employer withdraws the offer
    'unhire':      {'hired'},
}


@employer_verified_required
def application_update_status(request, app_id):
    """Single endpoint for view/accept/reject/hire transitions on an Application."""
    from django.http import JsonResponse
    from apps.jobs.models import Application
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST only'}, status=405)

    profile = request.user.employer_profile
    company = profile.company
    app = get_object_or_404(Application.objects.select_related('job'), id=app_id, job__company=company)

    action = (request.POST.get('action') or '').strip().lower()
    if action not in _ALLOWED_TRANSITIONS:
        return JsonResponse({'ok': False, 'error': 'Unknown action'}, status=400)

    if app.status not in _ALLOWED_TRANSITIONS[action]:
        # No-op for repeated views; explicit error for everything else.
        if action == 'view':
            return JsonResponse({'ok': True, 'status': app.status, 'noop': True})
        return JsonResponse({
            'ok': False,
            'error': f"Can't {action} an application that is already '{app.get_status_display()}'.",
        }, status=409)

    from django.utils import timezone
    from apps.jobseekers.models import WorkExperience
    now = timezone.now()
    update_fields = []

    if action == 'unhire':
        # Status stays 'hired' for historical record; stamp employed_until.
        if app.employed_until:
            return JsonResponse({'ok': False, 'error': 'Employment is already marked as ended.'}, status=409)
        # Optional explicit end date (accepts MM/DD/YYYY or 'Month D, YYYY'); default to today.
        end_raw = (request.POST.get('end_date') or '').strip()
        end_date = now.date()
        if end_raw:
            from datetime import datetime as _dt
            for fmt in ('%m/%d/%Y', '%B %d, %Y'):
                try:
                    end_date = _dt.strptime(end_raw, fmt).date()
                    break
                except ValueError:
                    continue
            if end_date > now.date():
                return JsonResponse({'ok': False, 'error': "End date can't be in the future."}, status=400)
            if app.hired_at and end_date < app.hired_at.date():
                return JsonResponse({'ok': False, 'error': "End date can't be before the hire date."}, status=400)
        app.employed_until = end_date
        update_fields.append('employed_until')
        # Re-open the slot since the employee is no longer occupying it.
        if app.job:
            app.job.slots = (app.job.slots or 0) + 1
            app.job.save(update_fields=['slots'])
        # End the linked work-experience entry (if it still exists).
        we = WorkExperience.objects.filter(from_application=app).first()
        if we and we.is_current:
            we.is_current = False
            we.month_ended = str(end_date.month)
            we.year_ended  = end_date.year
            we.save(update_fields=['is_current', 'month_ended', 'year_ended'])
        # Notify the jobseeker their employment was marked ended. The 'else'
        # branch below handles notifications for accept/reject/hire — this
        # is the parallel path for unhire.
        if app.jobseeker and app.jobseeker.user:
            from apps.notifications.models import Notification
            Notification.objects.create(
                recipient=app.jobseeker.user,
                notif_type=Notification.APPLICATION_UNHIRED,
                company=app.job.company if app.job else None,
                jobseeker=app.jobseeker,
                job=app.job,
            )
    else:
        # All other actions update the status field. Note: 'hire' moves into
        # the hire_pending offer state — no side effects yet. The slot
        # decrement and WorkExperience creation happen once the jobseeker
        # confirms via application_confirm_hire.
        status_for = {
            'view':        Application.STATUS_VIEWED,
            'accept':      Application.STATUS_ACCEPTED,
            'reject':      Application.STATUS_REJECTED,
            'hire':        Application.STATUS_HIRE_PENDING,
            'cancel_hire': Application.STATUS_ACCEPTED,
        }
        app.status = status_for[action]
        update_fields.append('status')

    app.save(update_fields=update_fields)

    # Notify the jobseeker on decision-points (skip 'view' and 'unhire').
    notif_for = {
        'accept':      'application_accepted',
        'reject':      'application_rejected',
        'hire':        'hire_offered',
        'cancel_hire': None,  # silent — employer withdrew before jobseeker saw it
    }
    if action in notif_for and notif_for[action]:
        from apps.notifications.models import Notification
        from apps.notifications.email import email_application_status_change
        Notification.objects.create(
            recipient=app.jobseeker.user,
            notif_type=notif_for[action],
            company=app.job.company,
            jobseeker=app.jobseeker,
            job=app.job,
        )
        # Best-effort transactional email.
        email_application_status_change(app, action)
    elif action == 'cancel_hire':
        # Clear the jobseeker's stale Hire Offered notification so they
        # don't see Accept/Decline buttons for an offer that's been pulled.
        from apps.notifications.models import Notification
        Notification.objects.filter(
            recipient=app.jobseeker.user,
            notif_type=Notification.HIRE_OFFERED,
            jobseeker=app.jobseeker, job=app.job, company=app.job.company,
            is_read=False,
        ).delete()

    return JsonResponse({
        'ok': True,
        'status': app.status,
        'status_label': app.get_status_display(),
        'employed_until': app.employed_until.isoformat() if app.employed_until else None,
    })

@employer_required
def company_profile(request):
    profile = request.user.employer_profile
    company = profile.company
    from apps.jobseekers.models import Sector
    from django.db.models import Count, Q
    sectors = Sector.objects.all()

    if request.method == 'POST':
        company.description = request.POST.get('description', '')
        company.nature_of_company = request.POST.get('nature_of_company', '')
        company.main_branch_address = request.POST.get('main_branch_address', '')
        company.iloilo_bldg_unit = request.POST.get('iloilo_bldg_unit', '')
        company.iloilo_street = request.POST.get('iloilo_street', '')
        company.iloilo_barangay_code = request.POST.get('iloilo_barangay', '')
        company.iloilo_barangay_name = request.POST.get('iloilo_barangay_name', '')
        company.save()

        sector_ids = request.POST.getlist('sectors')
        company.sector_badges.set(sector_ids)

        return redirect('/employers/profile/')

    # Job posts (with applicants + liked-by counts) for the card grid.
    # Excludes admin_disabled (PESO take-downs — don't belong on the public
    # profile) and deleted_at (soft-deleted jobs in the trash bin — same
    # rule as everywhere else in the app). Employer sees both on the
    # dedicated /jobs/ list with their own tabs; the profile card grid is
    # meant to show what a jobseeker would see.
    jobs = (
        JobPosting.objects.filter(
            company=company, admin_disabled=False, deleted_at__isnull=True,
        )
        .annotate(
            applicants_count=Count('applications', distinct=True),
            liked_by_count=Count(
                'jobseeker_interactions',
                filter=Q(jobseeker_interactions__interaction_type='liked'),
                distinct=True,
            ),
        )
        .select_related('experience_requirement')
        .prefetch_related('skill_requirements', 'certification_requirements', 'education_requirements')
        .order_by('-created_at')
    )

    followers_count = company.followers.count() if hasattr(company, 'followers') else 0

    from apps.jobs.models import Application
    hired_employees = (
        Application.objects.filter(job__company=company, status=Application.STATUS_HIRED)
        .select_related('jobseeker', 'job')
        .order_by('-hired_at', '-created_at')
    )

    return render(request, 'employers/company_profile.html', {
        'company': company,
        'profile': profile,
        'sectors': sectors,
        'jobs': jobs,
        'followers_count': followers_count,
        'hired_employees': hired_employees,
        'unread_notifications': False,
        'unread_messages': False,
    })

@employer_verified_required
def candidate_detail(request, jobseeker_id):
    from apps.matching.engine import compute_match_score
    profile = request.user.employer_profile
    company = profile.company
    jobseeker = get_object_or_404(JobseekerProfile, id=jobseeker_id)
    education = Education.objects.filter(profile=jobseeker)
    skills = Skill.objects.filter(profile=jobseeker)
    certifications = Certification.objects.filter(profile=jobseeker)
    experiences = WorkExperience.objects.filter(profile=jobseeker)
    is_liked = CandidateInteraction.objects.filter(
        company=company, jobseeker=jobseeker
    ).exists()

    # Currently-employed hire at this company (if any).
    from apps.jobs.models import Application, JobPosting
    active_hire = (
        Application.objects
        .filter(jobseeker=jobseeker, job__company=company,
                status=Application.STATUS_HIRED, employed_until__isnull=True)
        .select_related('job')
        .order_by('-hired_at')
        .first()
    )

    # Open jobs at this company — used in the Contact modal's "Re: which job?" dropdown.
    open_jobs = JobPosting.objects.filter(
        company=company, status=JobPosting.STATUS_OPEN
    ).order_by('-created_at')

    # Jobs this employer has ALREADY invited this jobseeker to apply for.
    # Sourced from the shared INVITED_TO_APPLY notification store — same
    # table the job_detail carousel and candidates-list checks read from,
    # so a "Sent" flip anywhere in the app reflects here too. The Contact
    # modal's Invite tab uses this to hide already-invited jobs from the
    # dropdown; the top-right Invite CTA hides entirely when the employer
    # has invited them to every open job.
    from apps.notifications.models import Notification
    invited_job_ids = set(
        Notification.objects.filter(
            notif_type=Notification.INVITED_TO_APPLY,
            company=company, jobseeker=jobseeker,
        ).values_list('job_id', flat=True)
    )
    invitable_open_jobs = [j for j in open_jobs if j.id not in invited_job_ids]

    # Has this jobseeker applied to ANY of this company's jobs? Gates the
    # Requirements + Interview tabs in the Contact modal so employers can't
    # send those messages to someone who hasn't applied yet — the message
    # copy assumes a live application to respond to.
    has_any_application = Application.objects.filter(
        jobseeker=jobseeker, job__company=company,
    ).exists()

    # Past contacts to this candidate from this company (most recent first).
    from apps.employers.models import EmployerContact
    past_contacts = EmployerContact.objects.filter(
        company=company, recipient=jobseeker
    ).order_by('-sent_at')[:5]

    # If the employer landed here from /employers/jobs/<id>/candidates/, we get
    # the job context via ?job=<id>. Use that to surface the application message
    # and offer Previous/Next nav across the applicant list for that job.
    # The ?job= query string carries a hashid (e.g. "qK4w2X"), not a raw
    # int — URL converters auto-decode path params but NOT query params, so
    # we decode by hand here. Falls back to raw int parsing for legacy links.
    job_id_raw = request.GET.get('job', '').strip()
    current_job = None
    application = None
    prev_id = None
    next_id = None
    match_score = None
    if job_id_raw:
        from apps.core.hashids import decode as _decode_hashid
        decoded = _decode_hashid(job_id_raw)
        if decoded is None and job_id_raw.isdigit():
            decoded = int(job_id_raw)  # legacy /?job=<int>
        if decoded is not None:
            try:
                current_job = JobPosting.objects.select_related('company').get(
                    id=decoded, company=company,
                )
            except JobPosting.DoesNotExist:
                current_job = None

    if current_job:
        application = (Application.objects
                       .filter(jobseeker=jobseeker, job=current_job)
                       .first())

        # Auto-bump pending → viewed when the employer opens the detail page.
        if application and application.status == Application.STATUS_PENDING:
            application.status = Application.STATUS_VIEWED
            application.save(update_fields=['status'])

        # Match score for the current job (admin sees the badge; everyone else
        # gets the number computed but it's hidden in the template).
        try:
            match_score = compute_match_score(current_job, jobseeker)
        except Exception:
            match_score = None

        # Build prev/next order. Which list to walk depends on where the
        # employer came from:
        #   ?from=recommended  → walk get_ranked_jobseekers() minus applicants
        #                        (mirrors the Recommended tab on candidates page)
        #   default            → walk Application.objects for this job
        #                        (mirrors the Applicants tab)
        # Without this split, Recommended-tab arrivals were always locked out
        # of Previous/Next because the ordering list only held applicants.
        _from_tab = (request.GET.get('from') or '').strip().lower()
        if _from_tab == 'recommended':
            from apps.matching.engine import get_ranked_jobseekers
            _applicant_ids = set(
                Application.objects.filter(job=current_job)
                .values_list('jobseeker_id', flat=True)
            )
            ordered_ids = [
                r['profile'].id
                for r in get_ranked_jobseekers(current_job)
                if r['profile'].id not in _applicant_ids
            ]
        else:
            ordered_ids = list(Application.objects
                               .filter(job=current_job)
                               .order_by('-created_at')
                               .values_list('jobseeker_id', flat=True))
        if jobseeker.id in ordered_ids:
            idx = ordered_ids.index(jobseeker.id)
            if idx > 0:
                prev_id = ordered_ids[idx - 1]
            if idx < len(ordered_ids) - 1:
                next_id = ordered_ids[idx + 1]

    return render(request, 'employers/candidate_detail.html', {
        'company': company,
        'jobseeker': jobseeker,
        'education': education,
        'skills': skills,
        'certifications': certifications,
        'experiences': experiences,
        'is_liked': is_liked,
        'active_hire': active_hire,
        'open_jobs': open_jobs,
        'invited_job_ids': invited_job_ids,
        'invitable_open_jobs': invitable_open_jobs,
        'has_any_application': has_any_application,
        'past_contacts': past_contacts,
        'can_see_badges': jobseeker.can_show_badges_to(company),
        'current_job': current_job,
        'application': application,
        'match_score': match_score,
        'prev_id': prev_id,
        'next_id': next_id,
        # `from` param propagated from the referring candidate card so the
        # back-link on this page (and the "counterpart tab" copy) matches
        # whichever list the employer arrived from.
        'from_tab': (request.GET.get('from') or '').strip().lower(),
        'unread_notifications': False,
        'unread_messages': False,
    })


@employer_verified_required
def candidate_like(request, jobseeker_id):
    if request.method != 'POST':
        return redirect('/employers/candidates/')
    profile = request.user.employer_profile
    company = profile.company
    jobseeker = get_object_or_404(JobseekerProfile, id=jobseeker_id)

    interaction = CandidateInteraction.objects.filter(
        company=company, jobseeker=jobseeker
    )
    if interaction.exists():
        # Unlike: drop the row and be done.
        interaction.delete()
    else:
        # Like: CandidateInteraction requires a job FK, so pin it to the
        # most recent open post for this company. If the company has no
        # open posts we no-op (the button just doesn't do anything) —
        # nothing to link the like to yet.
        from apps.jobs.models import JobPosting
        job = JobPosting.objects.filter(
            company=company, status='open', deleted_at__isnull=True,
        ).first()
        if job:
            CandidateInteraction.objects.create(
                company=company, jobseeker=jobseeker, job=job
            )

            from apps.notifications.utils import notify_company_liked_jobseeker, notify_match
            from apps.jobseekers.models import JobInteraction

            # Notify jobseeker that company liked them
            notify_company_liked_jobseeker(company, jobseeker, job)

            # Check for mutual match
            jobseeker_liked = JobInteraction.objects.filter(
                jobseeker=jobseeker, job=job, interaction_type='liked'
            ).exists()
            if jobseeker_liked:
                notify_match(company, jobseeker, job)

    # Always redirect — no matter which branch above we took (unlike,
    # like-with-job, or like-without-job). Previously the redirect was
    # nested inside the innermost "if job" so unlikes fell out returning
    # None → Django raised "view didn't return an HttpResponse".
    next_url = request.POST.get('next') or '/employers/candidates/'
    return redirect(next_url)


@employer_verified_required
@email_verified_required
def candidate_contact(request, jobseeker_id):
    """Employer sends an email (job requirements or interview schedule) to a
    jobseeker. Also creates an in-app bell notification."""
    if request.method != 'POST':
        return redirect(f'/employers/candidates/{_hashid(jobseeker_id)}/')

    from apps.employers.models import EmployerContact
    from apps.notifications.models import Notification
    from apps.notifications.email import email_employer_contact
    from apps.jobs.models import JobPosting
    from datetime import datetime
    from django.utils import timezone
    from django.contrib import messages

    profile = request.user.employer_profile
    company = profile.company
    jobseeker = get_object_or_404(JobseekerProfile, id=jobseeker_id)

    kind = (request.POST.get('kind') or '').strip()
    subject = (request.POST.get('subject') or '').strip()
    body = (request.POST.get('body') or '').strip()
    job_id_raw = (request.POST.get('job_id') or '').strip()
    interview_at_raw = (request.POST.get('interview_at') or '').strip()
    interview_location = (request.POST.get('interview_location') or '').strip()

    # "invite" is a UI-only shorthand for a REQUIREMENTS-shaped message —
    # different preset copy on the frontend, but stored as a plain contact.
    # Avoids a schema migration for what's effectively different boilerplate.
    # We keep the original UI intent in `ui_kind` because we need it below to
    # (a) enforce that invites are job-scoped and (b) dedupe against the
    # INVITED_TO_APPLY notification store so the invite-carousel guard on
    # job_detail.html and this modal share one source of truth.
    ui_kind = kind
    if kind == 'invite':
        kind = EmployerContact.KIND_REQUIREMENTS
    if kind not in (EmployerContact.KIND_REQUIREMENTS, EmployerContact.KIND_INTERVIEW):
        messages.error(request, 'Please pick a message type.')
        return redirect(f'/employers/candidates/{_hashid(jobseeker_id)}/')
    if not subject or not body:
        messages.error(request, 'Subject and body are required.')
        return redirect(f'/employers/candidates/{_hashid(jobseeker_id)}/')

    job = None
    if job_id_raw:
        job = JobPosting.objects.filter(id=job_id_raw, company=company).first()

    # Invite-to-apply guardrails: needs a specific job (otherwise "invited to
    # apply for what?"), and can't be sent twice for the same (jobseeker, job).
    if ui_kind == 'invite':
        if not job:
            messages.error(request, 'Pick a job to invite them to.')
            return redirect(f'/employers/candidates/{_hashid(jobseeker_id)}/')
        already_invited = Notification.objects.filter(
            notif_type=Notification.INVITED_TO_APPLY,
            company=company, jobseeker=jobseeker, job=job,
        ).exists()
        if already_invited:
            messages.info(
                request,
                f'You\'ve already invited {jobseeker.first_name} to apply for {job.title}.',
            )
            return redirect(f'/employers/candidates/{_hashid(jobseeker_id)}/')
    else:
        # Requirements / Interview: only valid AFTER the jobseeker has
        # applied to at least one of this company's jobs. Both message
        # types are follow-ups to a live application; sending them cold
        # doesn't make sense (and the message copy assumes an application
        # thread to respond to). Employers use Invite to Apply first.
        from apps.jobs.models import Application as _App
        has_application = _App.objects.filter(
            jobseeker=jobseeker, job__company=company,
        ).exists()
        if not has_application:
            kind_label = 'requirements' if kind == EmployerContact.KIND_REQUIREMENTS else 'interview details'
            messages.error(
                request,
                f'{jobseeker.first_name} hasn\'t applied to any of your jobs yet — '
                f'send an Invite to Apply first, then follow up with {kind_label} once they apply.',
            )
            return redirect(f'/employers/candidates/{_hashid(jobseeker_id)}/')

    interview_at = None
    if kind == EmployerContact.KIND_INTERVIEW and interview_at_raw:
        try:
            naive = datetime.strptime(interview_at_raw, '%Y-%m-%dT%H:%M')
            interview_at = timezone.make_aware(naive)
        except Exception:
            pass

    contact = EmployerContact.objects.create(
        sender=request.user,
        company=company,
        recipient=jobseeker,
        job=job,
        kind=kind,
        subject=subject,
        body=body,
        interview_at=interview_at,
        interview_location=interview_location if kind == EmployerContact.KIND_INTERVIEW else '',
    )

    # Email delivery is retired — every EmployerContact goes through the
    # in-app inbox + bell notification only. No SMTP attempts, no delivery
    # indicator, no timeouts. Jobseekers see the message in Inbox and get
    # a bell notification pointing them there.

    # In-app notification for the jobseeker.
    if jobseeker.user:
        kind_label = 'an invitation to apply' if ui_kind == 'invite' else (
            'job requirements' if kind == EmployerContact.KIND_REQUIREMENTS else 'interview details'
        )
        Notification.objects.create(
            recipient=jobseeker.user,
            notif_type=Notification.EMPLOYER_CONTACTED,
            company=company,
            jobseeker=jobseeker,
            job=job,
            liker_preview=kind_label,
            admin_message=subject,
        )
        # Also plant an INVITED_TO_APPLY marker for invites. This is the
        # shared idempotency store — same one job_detail.html's carousel
        # checks — so a follow-up click from either surface is a no-op.
        # We keep it minimal (no admin_message body) since the visible
        # bell item is the EMPLOYER_CONTACTED one above; this row is
        # here for the dedupe check, not for rendering.
        if ui_kind == 'invite':
            Notification.objects.create(
                recipient=jobseeker.user,
                notif_type=Notification.INVITED_TO_APPLY,
                company=company, jobseeker=jobseeker, job=job,
                liker_preview=job.title,
                is_read=True,  # silent marker — don't inflate unread count
            )

    if ui_kind == 'invite' and job:
        messages.success(
            request,
            f'Success! {jobseeker.first_name} {jobseeker.last_name} has received your Invitation to Apply as {job.title}.',
        )
    else:
        messages.success(request, f'Sent to {jobseeker.first_name}\'s EasyHire inbox.')
    # Bounce back to wherever the employer came from — job detail, candidate
    # list, inbox, etc. Falls back to the candidate profile when the caller
    # didn't provide a next hint. Same-origin check: only accept paths that
    # start with '/employers/' so we can't be redirected off-site.
    next_url = (request.POST.get('next') or '').strip()
    if next_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(next_url)
            if parsed.netloc and parsed.netloc != request.get_host():
                next_url = ''
            elif parsed.path and not parsed.path.startswith('/employers/'):
                next_url = ''
        except Exception:
            next_url = ''
    if not next_url:
        next_url = f'/employers/candidates/{_hashid(jobseeker_id)}/'
    return redirect(next_url)


# Analytics for employers is served by apps/analytics/views.analytics,
# which forks by user type and renders templates/employers/analytics.html
# (a thin wrapper around templates/analytics/_dashboard_body.html).
# No duplicate view needed here.

@employer_verified_required
def all_candidates(request):
    from apps.matching.engine import get_ranked_jobseekers
    from apps.jobseekers.models import JobseekerProfile
    profile = request.user.employer_profile
    company = profile.company

    search = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'name')

    liked_ids = list(CandidateInteraction.objects.filter(
        company=company
    ).values_list('jobseeker_id', flat=True))

    # Honor privacy: hide deactivated accounts AND profiles that opted to
    # disappear after being tagged Hired.
    hidden_after_hire_ids = (
        JobseekerProfile.objects
        .filter(profile_visibility='hidden', applications__status='hired')
        .values_list('id', flat=True).distinct()
    )
    candidates = (
        JobseekerProfile.objects
        .filter(profile_complete=True, user__is_active=True)
        .exclude(id__in=hidden_after_hire_ids)
    )

    if search:
        candidates = candidates.filter(
            first_name__icontains=search
        ) | candidates.filter(
            last_name__icontains=search
        ) | candidates.filter(
            skills__name__icontains=search
        )
        candidates = candidates.distinct()

    if sort == 'name':
        candidates = candidates.order_by('first_name', 'last_name')
    elif sort == 'recent':
        candidates = candidates.order_by('-created_at')

    total = candidates.count()
    # Materialize and annotate per-candidate badge visibility so the template
    # can decide what to render without re-querying.
    candidates = list(candidates.prefetch_related('sectors'))
    for cand in candidates:
        cand.show_badges = cand.can_show_badges_to(company)

    # All-candidates view doesn't compute per-pair scores (no specific job in
    # context), so only pagination applies — no poor-match toggle here.
    from apps.core.pagination import paginate, querystring_without
    page = paginate(request, candidates, per_page=12)

    return render(request, 'employers/all_candidates.html', {
        'company': company,
        'candidates': list(page.object_list),
        'liked_ids': liked_ids,
        'search': search,
        'sort': sort,
        'total': total,
        'page': page,
        'qs_base': querystring_without(request, 'page'),
        'unread_notifications': False,
        'unread_messages': False,
    })


@employer_required
def employer_settings(request):
    """Employer-side settings: edit representative info, edit company contact
    info, change password, deactivate.

    Two independent sections:
      - Representative info (all editable via Edit toggle in the template)
      - Company info: contact fields editable; name/type/nature locked
        (admin-only, requires re-verification with additional docs).
    """
    from django.db import IntegrityError
    profile = request.user.employer_profile
    company = profile.company
    saved_section = None
    error = None

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'representative':
            # Rep name + position + phone + email. Sex + birthdate removed —
            # not needed for the rep record.
            profile.first_name  = request.POST.get('first_name',  profile.first_name).strip()
            profile.middle_name = request.POST.get('middle_name', '').strip()
            profile.last_name   = request.POST.get('last_name',   profile.last_name).strip()
            profile.suffix      = request.POST.get('suffix',      '').strip()
            profile.position    = request.POST.get('position',    profile.position).strip()
            profile.phone       = request.POST.get('phone',       profile.phone).strip()
            profile.email       = request.POST.get('rep_contact_email', profile.email).strip()

            # Login email (User.email). Enforce uniqueness manually since a
            # duplicate would raise IntegrityError deep in save() — friendlier
            # to catch it here and surface a form error.
            new_login_email = (request.POST.get('rep_login_email') or '').strip()
            if new_login_email and new_login_email != request.user.email:
                from apps.accounts.models import User
                if User.objects.filter(email__iexact=new_login_email).exclude(pk=request.user.pk).exists():
                    error = 'That login email is already in use by another EasyHire account.'
                else:
                    request.user.email = new_login_email
                    try:
                        request.user.save(update_fields=['email'])
                    except IntegrityError:
                        error = 'That login email is already in use by another EasyHire account.'

            if error is None:
                profile.save()
                saved_section = 'representative'

        elif form_type == 'company_contact':
            # Only the contact fields on Company are editable from here —
            # name / type_of_company / nature_of_company stay admin-only.
            company.company_email     = request.POST.get('company_email',     company.company_email).strip()
            company.recruitment_email = request.POST.get('recruitment_email', company.recruitment_email).strip()
            company.save(update_fields=['company_email', 'recruitment_email'])
            saved_section = 'company_contact'

        elif form_type == 'sectors':
            # PESO-approved sector change. Store the requested set on the
            # pending M2M + flip the flag; admin approves or denies from
            # the admin panel. Employers can also cancel their own pending
            # request by submitting an empty selection alongside a
            # `cancel_pending` marker.
            from apps.jobseekers.models import Sector
            from django.utils import timezone
            if request.POST.get('cancel_pending') == '1':
                company.pending_sector_badges.clear()
                company.sectors_change_pending = False
                company.sectors_change_requested_at = None
                company.save(update_fields=[
                    'sectors_change_pending', 'sectors_change_requested_at',
                ])
                saved_section = 'sectors_cancelled'
            else:
                requested = request.POST.getlist('sectors')
                sectors = Sector.objects.filter(id__in=requested)
                company.pending_sector_badges.set(sectors)
                company.sectors_change_pending = True
                company.sectors_change_requested_at = timezone.now()
                company.save(update_fields=[
                    'sectors_change_pending', 'sectors_change_requested_at',
                ])
                saved_section = 'sectors'

    from apps.jobseekers.models import Sector
    all_sectors = Sector.objects.all().order_by('label')

    return render(request, 'employers/settings.html', {
        'profile': profile,
        'company': company,
        'user': request.user,
        'saved_section': saved_section,
        'error': error,
        'all_sectors': all_sectors,
        'unread_notifications': False,
        'unread_messages': False,
    })