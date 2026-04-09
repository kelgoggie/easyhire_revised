from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.employers.models import Company, VerificationDocument
from apps.jobseekers.models import JobseekerProfile, Education, Skill, Certification, WorkExperience
from apps.employers.models import CandidateInteraction


def landing(request):
    return render(request, 'employers/landing.html')


def employer_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/employers/login/')
        if not request.user.is_employer:
            return redirect('/employers/login/')
        try:
            profile = request.user.employer_profile
            if not profile.company.is_verified:
                return redirect('/employers/pending/')
        except Exception:
            return redirect('/employers/register/')
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
    recent_jobs = JobPosting.objects.filter(company=company).order_by('-created_at')[:5]

    return render(request, 'employers/dashboard.html', {
        'profile': profile,
        'company': company,
        'recent_jobs': recent_jobs,
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
        )
    )

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

@employer_required
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

        # Education requirement
        edu_level = request.POST.get('edu_level')
        if edu_level:
            JobEducationRequirement.objects.create(
                job=job,
                level=edu_level,
                course_degree=request.POST.get('edu_course', ''),
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

    return render(request, 'employers/job_form.html', {
        'company': company,
        'action': 'Create',
        'job': None,
        'unread_notifications': False,
        'unread_messages': False,
    })



@employer_required
def job_edit(request, job_id):
    profile = request.user.employer_profile
    company = profile.company
    job = get_object_or_404(JobPosting, id=job_id, company=company)

    if request.method == 'POST':
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

        # Education
        JobEducationRequirement.objects.filter(job=job).delete()
        edu_level = request.POST.get('edu_level')
        if edu_level:
            JobEducationRequirement.objects.create(
                job=job,
                level=edu_level,
                course_degree=request.POST.get('edu_course', ''),
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
        'unread_notifications': False,
        'unread_messages': False,
    })


@employer_required
def job_delete(request, job_id):
    profile = request.user.employer_profile
    job = get_object_or_404(JobPosting, id=job_id, company=profile.company)
    if request.method == 'POST':
        job.delete()
    return redirect('/employers/jobs/')

    
@employer_required
def job_detail(request, job_id):
    profile = request.user.employer_profile
    company = profile.company
    job = get_object_or_404(JobPosting, id=job_id, company=company)

    return render(request, 'employers/job_detail.html', {
        'company': company,
        'job': job,
        'unread_notifications': False,
        'unread_messages': False,
    })


@employer_required
def candidates(request, job_id):
    from apps.matching.engine import get_ranked_jobseekers
    from apps.jobseekers.models import JobInteraction
    profile = request.user.employer_profile
    company = profile.company
    job = get_object_or_404(JobPosting, id=job_id, company=company)
    tab = request.GET.get('tab', 'recommended')

    liked_ids = list(CandidateInteraction.objects.filter(
        company=company, job=job
    ).values_list('jobseeker_id', flat=True))

    
    # Jobseekers who liked this job
    liked_by_jobseeker_ids = list(JobInteraction.objects.filter(
        job=job, interaction_type=JobInteraction.LIKED
    ).values_list('jobseeker_id', flat=True))

    liked_by_count = len(liked_by_jobseeker_ids)

    if tab == 'liked_by':
        from apps.jobseekers.models import JobseekerProfile
        from apps.matching.engine import compute_match_score
        jobseekers_raw = JobseekerProfile.objects.filter(id__in=liked_by_jobseeker_ids)
        ranked = []
        for js in jobseekers_raw:
            score_data = compute_match_score(job, js)
            ranked.append({
                'profile': js,
                'score': score_data['total'],
                'breakdown': score_data['breakdown'],
            })
        ranked.sort(key=lambda x: x['score'], reverse=True)

    elif tab == 'liked':
        from apps.jobseekers.models import JobseekerProfile
        jobseekers_raw = JobseekerProfile.objects.filter(id__in=liked_ids)
        ranked = [{'profile': js, 'score': None, 'breakdown': {}} for js in jobseekers_raw]

    elif tab == 'applicants':
        ranked = []

    else:
        ranked = get_ranked_jobseekers(job)

    return render(request, 'employers/candidates.html', {
        'company': company,
        'job': job,
        'ranked': ranked,
        'liked_ids': liked_ids,
        'liked_by_count': liked_by_count,
        'tab': tab,
        'unread_notifications': False,
        'unread_messages': False,
    })

@employer_required
def company_profile(request):
    profile = request.user.employer_profile
    company = profile.company
    from apps.jobseekers.models import Sector
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

    return render(request, 'employers/company_profile.html', {
        'company': company,
        'profile': profile,
        'sectors': sectors,
        'unread_notifications': False,
        'unread_messages': False,
    })

@employer_required
def candidate_detail(request, jobseeker_id):
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

    return render(request, 'employers/candidate_detail.html', {
        'company': company,
        'jobseeker': jobseeker,
        'education': education,
        'skills': skills,
        'certifications': certifications,
        'experiences': experiences,
        'is_liked': is_liked,
        'unread_notifications': False,
        'unread_messages': False,
    })


@employer_required
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

@employer_required
def analytics(request):
    profile = request.user.employer_profile
    company = profile.company

    # Import the analytics view logic from the existing analytics app
    from apps.analytics.views import get_analytics_context
    context = get_analytics_context(request)
    context.update({
        'company': company,
        'unread_notifications': False,
        'unread_messages': False,
    })
    return render(request, 'employers/analytics.html', context)

@employer_required
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

    candidates = JobseekerProfile.objects.filter(profile_complete=True)

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

    return render(request, 'employers/all_candidates.html', {
        'company': company,
        'candidates': candidates,
        'liked_ids': liked_ids,
        'search': search,
        'sort': sort,
        'total': candidates.count(),
        'unread_notifications': False,
        'unread_messages': False,
    })