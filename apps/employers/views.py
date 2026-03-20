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
    profile = request.user.employer_profile
    company = profile.company
    query = request.GET.get('q', '')
    jobs = JobPosting.objects.filter(company=company)
    if query:
        jobs = jobs.filter(title__icontains=query)

    return render(request, 'employers/job_list.html', {
        'company': company,
        'jobs': jobs,
        'query': query,
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
            street_barangay=request.POST.get('street_barangay', ''),
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
        years = request.POST.get('exp_years')
        if years:
            JobExperienceRequirement.objects.create(
                job=job,
                years_required=years,
                description=request.POST.get('exp_description', ''),
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
def job_detail(request, job_id):
    profile = request.user.employer_profile
    job = get_object_or_404(JobPosting, id=job_id, company=profile.company)
    return render(request, 'employers/job_detail.html', {
        'job': job,
        'company': profile.company,
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
        job.street_barangay = request.POST.get('street_barangay', '')
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
        years = request.POST.get('exp_years')
        if years:
            JobExperienceRequirement.objects.create(
                job=job,
                years_required=years,
                description=request.POST.get('exp_description', ''),
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
def candidates(request):
    from apps.matching.engine import get_ranked_jobseekers
    profile = request.user.employer_profile
    company = profile.company
    tab = request.GET.get('tab', 'recommended')

    liked_ids = list(CandidateInteraction.objects.filter(
        company=company
    ).values_list('jobseeker_id', flat=True))

    if tab == 'liked':
        from apps.jobseekers.models import JobseekerProfile
        jobseekers_raw = JobseekerProfile.objects.filter(id__in=liked_ids)
        ranked = [{'profile': js, 'score': None, 'breakdown': {}} for js in jobseekers_raw]
    elif tab == 'applicants':
        ranked = []
    else:
        # Get the company's most recent open job to rank against
        from apps.jobs.models import JobPosting
        job = JobPosting.objects.filter(
            company=company, status='open'
        ).first()
        if job:
            ranked = get_ranked_jobseekers(job)
        else:
            from apps.jobseekers.models import JobseekerProfile
            jobseekers_raw = JobseekerProfile.objects.filter(profile_complete=True)
            ranked = [{'profile': js, 'score': None, 'breakdown': {}} for js in jobseekers_raw]

    return render(request, 'employers/candidates.html', {
        'company': company,
        'ranked': ranked,
        'liked_ids': liked_ids,
        'tab': tab,
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

    next_url = request.POST.get('next', '/employers/candidates/')
    return redirect(next_url)