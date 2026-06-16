from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.employers.models import Company, VerificationDocument
from apps.jobseekers.models import JobseekerProfile, Education, Skill, Certification, WorkExperience
from apps.employers.models import CandidateInteraction


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
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/employers/login/')
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


@login_required(login_url='/employers/login/')
def pending(request):
    if not request.user.is_employer:
        return redirect('/employers/login/')
    try:
        profile = request.user.employer_profile
        company = profile.company
    except Exception:
        return redirect('/employers/register/')

    if company.is_verified:
        return redirect('/employers/dashboard/')

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

    return render(request, 'employers/pending.html', {
        'company': company,
        'profile': profile,
        'checklist': checklist,
        'all_uploaded': all(item['uploaded'] for item in checklist),
    })


@login_required(login_url='/employers/login/')
def upload_document(request):
    if request.method != 'POST':
        return redirect('/employers/pending/')
    try:
        company = request.user.employer_profile.company
    except Exception:
        return redirect('/employers/register/')

    doc_type = request.POST.get('doc_type')
    file = request.FILES.get('file')
    if doc_type and file:
        VerificationDocument.objects.filter(company=company, doc_type=doc_type).delete()
        VerificationDocument.objects.create(company=company, doc_type=doc_type, file=file)

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

    jobs = JobPosting.objects.filter(company=company).annotate(
        liked_by_count=Count(
            'jobseeker_interactions',
            filter=Q(jobseeker_interactions__interaction_type='liked')
        ),
        applicants_count=Count('applications', distinct=True),
    ).select_related('experience_requirement'
    ).prefetch_related('skill_requirements', 'certification_requirements', 'education_requirements')

    if query:
        jobs = jobs.filter(title__icontains=query)
    if status_filter:
        jobs = jobs.filter(status=status_filter)
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
        'unread_notifications': False,
        'unread_messages': False,
    })

@employer_verified_required
def job_create(request):
    profile = request.user.employer_profile
    company = profile.company

    if request.method == 'POST':
        # Core job
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
            JobExperienceRequirement.objects.create(
                job=job,
                months_required=months,
                description=request.POST.get('exp_description', ''),
                any_experience_accepted='any_experience_accepted' in request.POST,
                preferred_position=request.POST.get('exp_preferred_position', ''),
            )
        return redirect('/employers/jobs/')

    # Prefill location with the company's Iloilo branch address as the default
    location_defaults = {
        'bldg_unit': company.iloilo_bldg_unit or '',
        'street': company.iloilo_street or '',
        'barangay_code': company.iloilo_barangay_code or '',
        'barangay_name': company.iloilo_barangay_name or '',
    }
    return render(request, 'employers/job_form.html', {
        'company': company,
        'action': 'Create',
        'job': None,
        'location_defaults': location_defaults,
        'unread_notifications': False,
        'unread_messages': False,
    })



@employer_verified_required
def job_edit(request, job_id):
    profile = request.user.employer_profile
    company = profile.company
    job = get_object_or_404(JobPosting, id=job_id, company=company)

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
            JobExperienceRequirement.objects.create(
                job=job,
                months_required=months,
                description=request.POST.get('exp_description', ''),
                any_experience_accepted='any_experience_accepted' in request.POST,
                preferred_position=request.POST.get('exp_preferred_position', ''),
            )

        return redirect('/employers/jobs/')

    return render(request, 'employers/job_form.html', {
        'company': company,
        'action': 'Edit',
        'job': job,
        # All edit-mode prefills come from `job.*`; this empty dict just keeps
        # the template's `|default:location_defaults.*` chain from raising.
        'location_defaults': {'bldg_unit': '', 'street': '', 'barangay_code': '', 'barangay_name': ''},
        'unread_notifications': False,
        'unread_messages': False,
    })


@employer_verified_required
def job_delete(request, job_id):
    profile = request.user.employer_profile
    job = get_object_or_404(JobPosting, id=job_id, company=profile.company)
    if request.method == 'POST':
        job.delete()
    return redirect('/employers/jobs/')


@employer_verified_required
def job_close(request, job_id):
    """Toggle a job between OPEN and CLOSED. Closed jobs hide from jobseeker
    recommendations and stop receiving new applications, but stay on record."""
    profile = request.user.employer_profile
    job = get_object_or_404(JobPosting, id=job_id, company=profile.company)
    if request.method == 'POST':
        if job.status == JobPosting.STATUS_OPEN:
            job.status = JobPosting.STATUS_CLOSED
        elif job.status == JobPosting.STATUS_CLOSED:
            job.status = JobPosting.STATUS_OPEN
        job.save(update_fields=['status'])
    return redirect(request.POST.get('next') or '/employers/jobs/')

    
@employer_required
def job_detail(request, job_id):
    from apps.matching.engine import get_ranked_jobseekers
    from apps.jobs.models import Application
    from apps.employers.models import EmployerContact

    profile = request.user.employer_profile
    company = profile.company
    job = get_object_or_404(JobPosting, id=job_id, company=company)

    # Top ranked jobseekers for this job (excluding people who already applied).
    applicant_ids = set(Application.objects.filter(job=job).values_list('jobseeker_id', flat=True))
    ranked = get_ranked_jobseekers(job)
    ranked = [r for r in ranked if r['profile'].id not in applicant_ids][:8]

    # Jobseekers who have already been invited to apply for this job.
    invited_ids = set(EmployerContact.objects.filter(
        company=company, job=job, kind=EmployerContact.KIND_REQUIREMENTS,
    ).values_list('recipient_id', flat=True))

    return render(request, 'employers/job_detail.html', {
        'company': company,
        'job': job,
        'ranked': ranked,
        'invited_ids': invited_ids,
        'applicants_count': len(applicant_ids),
        'unread_notifications': False,
        'unread_messages': False,
    })


@employer_verified_required
def invite_to_apply(request, job_id, jobseeker_id):
    """Send a jobseeker an email + bell notification inviting them to apply for
    a specific job. Idempotent — won't double-send to the same jobseeker.
    """
    from django.http import JsonResponse
    from django.contrib import messages as flash
    from apps.jobseekers.models import JobseekerProfile
    from apps.employers.models import EmployerContact
    from apps.notifications.models import Notification
    from apps.notifications.email import _send

    if request.method != 'POST':
        return redirect(f'/employers/jobs/{job_id}/')

    profile = request.user.employer_profile
    company = profile.company
    job = get_object_or_404(JobPosting, id=job_id, company=company)
    jobseeker = get_object_or_404(JobseekerProfile, id=jobseeker_id)

    # Skip if already invited (idempotent).
    already = EmployerContact.objects.filter(
        company=company, job=job, recipient=jobseeker,
        kind=EmployerContact.KIND_REQUIREMENTS,
    ).exists()

    if not already:
        subject = f'Invitation to apply — {job.title} at {company.name}'
        body = (
            f"Hi {jobseeker.first_name},\n\n"
            f"{company.name} thinks you'd be a great fit for our open {job.title} role and would like to invite you to apply.\n\n"
            f"View the full job posting and submit your application on EasyHire:\n"
            f"https://easyhire-iloilo.onrender.com/jobs/{job.id}/\n\n"
            f"— {company.name} Recruitment Team"
        )

        # Record as an EmployerContact (kind=requirements is closest fit).
        contact = EmployerContact.objects.create(
            sender=request.user, company=company, recipient=jobseeker, job=job,
            kind=EmployerContact.KIND_REQUIREMENTS,
            subject=subject, body=body,
        )

        # Email the jobseeker.
        to_email = jobseeker.contact_email or (jobseeker.user.email if jobseeker.user else '')
        if to_email:
            _send(to_email, subject, body)
            contact.delivered_to_email = to_email
            contact.save(update_fields=['delivered_to_email'])

        # Bell notification.
        if jobseeker.user:
            Notification.objects.create(
                recipient=jobseeker.user,
                notif_type=Notification.EMPLOYER_CONTACTED,
                company=company, jobseeker=jobseeker, job=job,
                liker_preview=f'an invitation to apply for {job.title}',
                admin_message=subject,
            )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'already': already})

    if already:
        flash.info(request, f'{jobseeker.first_name} has already been invited.')
    else:
        flash.success(request, f'Invitation sent to {jobseeker.first_name}.')
    return redirect(f'/employers/jobs/{job_id}/')


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

    liked_ids = list(CandidateInteraction.objects.filter(
        company=company, job=job
    ).values_list('jobseeker_id', flat=True))

    # Counts for tab labels
    applicants_count = Application.objects.filter(job=job).count()
    liked_by_count = JobInteraction.objects.filter(
        job=job, interaction_type=JobInteraction.LIKED
    ).count()

    if tab == 'recommended':
        ranked = get_ranked_jobseekers(job)
        # Hide people who already applied so the lists complement each other
        applicant_ids = set(Application.objects.filter(job=job).values_list('jobseeker_id', flat=True))
        ranked = [r for r in ranked if r['profile'].id not in applicant_ids]

    else:  # 'applicants' (default)
        apps = (Application.objects.filter(job=job)
                .select_related('jobseeker')
                .order_by('-created_at'))
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
        ranked.sort(key=lambda x: -x['score'])

    from apps.core.pagination import paginate, querystring_without
    page = paginate(request, ranked, per_page=12)

    return render(request, 'employers/candidates.html', {
        'company': company,
        'job': job,
        'ranked': list(page.object_list),
        'liked_ids': liked_ids,
        'liked_by_count': liked_by_count,
        'applicants_count': applicants_count,
        'tab': tab,
        'page': page,
        'qs_base': querystring_without(request, 'page'),
        'unread_notifications': False,
        'unread_messages': False,
    })


# Valid transitions enforced server-side. Rejected is terminal.
# Hired stays as status='hired' even after un-hire (un-hire = "employment ended"),
# we just stamp employed_until and end the linked work-experience entry.
_ALLOWED_TRANSITIONS = {
    # action -> set of statuses we'll accept this action from
    'view':   {'pending'},
    'accept': {'pending', 'viewed'},
    'reject': {'pending', 'viewed', 'accepted'},  # accepted can be reverted
    'hire':   {'accepted'},
    'unhire': {'hired'},  # marks employment as ended; status stays 'hired' for history
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
    else:
        # All other actions update the status field.
        status_for = {
            'view':   Application.STATUS_VIEWED,
            'accept': Application.STATUS_ACCEPTED,
            'reject': Application.STATUS_REJECTED,
            'hire':   Application.STATUS_HIRED,
        }
        app.status = status_for[action]
        update_fields.append('status')
        if action == 'hire':
            if not app.hired_at:
                app.hired_at = now
                update_fields.append('hired_at')
            # Decrement the job's open slots (clamped at 0).
            if app.job and (app.job.slots or 0) > 0:
                app.job.slots -= 1
                app.job.save(update_fields=['slots'])
            # Auto-create a work-experience entry on the jobseeker's resume
            # (idempotent — only one per application).
            if not WorkExperience.objects.filter(from_application=app).exists():
                WorkExperience.objects.create(
                    profile=app.jobseeker,
                    position=app.job.title,
                    company=app.job.company.name,
                    description='',
                    month_started=str(now.month),
                    year_started=now.year,
                    is_current=True,
                    from_application=app,
                )

    app.save(update_fields=update_fields)

    # Notify the jobseeker on decision-points (skip 'view' and 'unhire').
    notif_for = {
        'accept': 'application_accepted',
        'reject': 'application_rejected',
        'hire':   'application_hired',
    }
    if action in notif_for:
        from apps.notifications.models import Notification
        from apps.notifications.email import email_application_status_change
        Notification.objects.create(
            recipient=app.jobseeker.user,
            notif_type=notif_for[action],
            company=app.job.company,
            job=app.job,
        )
        # Best-effort transactional email.
        email_application_status_change(app, action)

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

    # Job posts (with applicants + liked-by counts) for the card grid
    jobs = (
        JobPosting.objects.filter(company=company)
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

    # Past contacts to this candidate from this company (most recent first).
    from apps.employers.models import EmployerContact
    past_contacts = EmployerContact.objects.filter(
        company=company, recipient=jobseeker
    ).order_by('-sent_at')[:5]

    # If the employer landed here from /employers/jobs/<id>/candidates/, we get
    # the job context via ?job=<id>. Use that to surface the application message
    # and offer Previous/Next nav across the applicant list for that job.
    job_id_raw = request.GET.get('job', '').strip()
    current_job = None
    application = None
    prev_id = None
    next_id = None
    match_score = None
    if job_id_raw:
        try:
            current_job = JobPosting.objects.select_related('company').get(
                id=job_id_raw, company=company,
            )
        except (JobPosting.DoesNotExist, ValueError):
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

        # Build applicant order — same sort as the candidates page.
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
        'past_contacts': past_contacts,
        'can_see_badges': jobseeker.can_show_badges_to(company),
        'current_job': current_job,
        'application': application,
        'match_score': match_score,
        'prev_id': prev_id,
        'next_id': next_id,
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
        interaction.delete()
    else:
        # CandidateInteraction requires a job — use the most recent open job
        from apps.jobs.models import JobPosting
        job = JobPosting.objects.filter(
            company=company, status='open'
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
                
            next_url = request.POST.get('next', '/employers/candidates/')
            return redirect(next_url)


@employer_verified_required
def candidate_contact(request, jobseeker_id):
    """Employer sends an email (job requirements or interview schedule) to a
    jobseeker. Also creates an in-app bell notification."""
    if request.method != 'POST':
        return redirect(f'/employers/candidates/{jobseeker_id}/')

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

    if kind not in (EmployerContact.KIND_REQUIREMENTS, EmployerContact.KIND_INTERVIEW):
        messages.error(request, 'Please pick a message type.')
        return redirect(f'/employers/candidates/{jobseeker_id}/')
    if not subject or not body:
        messages.error(request, 'Subject and body are required.')
        return redirect(f'/employers/candidates/{jobseeker_id}/')

    job = None
    if job_id_raw:
        job = JobPosting.objects.filter(id=job_id_raw, company=company).first()

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

    # Send the email (gracefully no-ops on SMTP failure).
    email_employer_contact(contact)

    # In-app notification for the jobseeker.
    if jobseeker.user:
        kind_label = 'job requirements' if kind == EmployerContact.KIND_REQUIREMENTS else 'interview details'
        Notification.objects.create(
            recipient=jobseeker.user,
            notif_type=Notification.EMPLOYER_CONTACTED,
            company=company,
            jobseeker=jobseeker,
            job=job,
            liker_preview=kind_label,
            admin_message=subject,
        )

    messages.success(request, f'Your message has been sent to {jobseeker.first_name}.')
    return redirect(f'/employers/candidates/{jobseeker_id}/')


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
    """Employer-side settings: edit representative info, change password, deactivate.

    Mirrors the jobseeker settings page but without the PESO-review workflow —
    employer reps can edit their info directly.
    """
    from datetime import datetime
    profile = request.user.employer_profile
    saved_section = None

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'personal':
            profile.first_name  = request.POST.get('first_name',  profile.first_name).strip()
            profile.middle_name = request.POST.get('middle_name', '').strip()
            profile.last_name   = request.POST.get('last_name',   profile.last_name).strip()
            profile.suffix      = request.POST.get('suffix',      '').strip()
            profile.position    = request.POST.get('position',    profile.position).strip()
            profile.phone       = request.POST.get('phone',       profile.phone).strip()
            sex = request.POST.get('sex', '').strip()
            if sex in {'M', 'F'}:
                profile.sex = sex
            dob_raw = request.POST.get('date_of_birth', '').strip()
            if dob_raw:
                for fmt in ('%m/%d/%Y', '%B %d, %Y'):
                    try:
                        profile.birthday = datetime.strptime(dob_raw, fmt).date()
                        break
                    except ValueError:
                        continue
            profile.save()
            saved_section = 'personal'

    return render(request, 'employers/settings.html', {
        'profile': profile,
        'company': profile.company,
        'saved_section': saved_section,
        'unread_notifications': False,
        'unread_messages': False,
    })