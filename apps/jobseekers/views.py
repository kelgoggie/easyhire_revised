from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.jobs.models import JobPosting
from apps.jobseekers.models import (
    JobseekerProfile, Education, Skill,
    Certification, WorkExperience, Sector
)
from datetime import datetime
import json
from django.http import JsonResponse
from django.db.models import Q


@login_required
def dashboard(request):
    if not request.user.is_jobseeker:
        return redirect('/employers/dashboard/')

    try:
        profile = request.user.jobseeker_profile
    except JobseekerProfile.DoesNotExist:
        return redirect('/register/info/')

    from apps.matching.engine import get_ranked_jobs
    from apps.jobs.models import Application

    education = Education.objects.filter(profile=profile)
    skills = Skill.objects.filter(profile=profile)
    certifications = Certification.objects.filter(profile=profile)

    if profile.profile_complete:
        ranked_jobs = get_ranked_jobs(profile)[:5]
    else:
        ranked_jobs = JobPosting.objects.filter(status='open').order_by('-created_at').select_related('company')[:5]
        ranked_jobs = [{'job': j, 'score': None} for j in ranked_jobs]

    applications = (
        Application.objects
        .filter(jobseeker=profile)
        .select_related('job', 'job__company')
        .order_by('-created_at')[:5]
    )

    # Gather recent open jobs from followed companies
    followed_companies = profile.followed_companies.all()
    followed_jobs = []
    for company in followed_companies:
        jobs = company.job_postings.filter(status='open').order_by('-created_at')[:2]
        for job in jobs:
            followed_jobs.append({'company': company, 'job': job})
        if len(followed_jobs) >= 6:
            break

    return render(request, 'jobseekers/dashboard.html', {
        'profile': profile,
        'education': education,
        'skills': skills,
        'certifications': certifications,
        'ranked_jobs': ranked_jobs,
        'applications': applications,
        'followed_jobs': followed_jobs,
        'unread_notifications': False,
        'unread_messages': False,
    })


@login_required
def parse_resume_pdf(request):
    """Accept an uploaded PDF, extract structured fields, return JSON for the
    resume form to pre-fill. Skill matching uses the existing Skill catalog."""
    if request.method != 'POST' or not request.user.is_jobseeker:
        return JsonResponse({'ok': False, 'error': 'Bad request'}, status=400)

    pdf = request.FILES.get('resume_pdf')
    if not pdf:
        return JsonResponse({'ok': False, 'error': 'No file provided'}, status=400)
    if pdf.size > 10 * 1024 * 1024:
        return JsonResponse({'ok': False, 'error': 'File must be under 10 MB'}, status=400)
    if not pdf.name.lower().endswith('.pdf'):
        return JsonResponse({'ok': False, 'error': 'Only PDF files are supported'}, status=400)

    from apps.jobseekers.resume_parser import parse_resume
    # Build the known-skills list from existing Skill rows so matching reflects
    # what other jobseekers have already entered. Cap to keep the loop tight.
    known_skills = list(
        Skill.objects.values_list('name', flat=True).distinct()[:2000]
    )

    try:
        result = parse_resume(pdf.read(), known_skills=known_skills)
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'Parsing failed: {e}'}, status=500)

    return JsonResponse(result)


@login_required
def profile_view(request):
    if not request.user.is_jobseeker:
        return redirect('/employers/dashboard/')
    try:
        profile = request.user.jobseeker_profile
    except JobseekerProfile.DoesNotExist:
        return redirect('/register/info/')

    experiences = WorkExperience.objects.filter(profile=profile).order_by('-year_started', '-id')
    skills = Skill.objects.filter(profile=profile)
    education = Education.objects.filter(profile=profile)
    certifications = Certification.objects.filter(profile=profile)
    followed_count = profile.followed_companies.count()

    return render(request, 'jobseekers/profile.html', {
        'profile': profile,
        'experiences': experiences,
        'skills': skills,
        'education': education,
        'certifications': certifications,
        'followed_count': followed_count,
    })


@login_required
def profile_picture_upload(request):
    """Accepts an uploaded (already-cropped) image and saves it."""
    if request.method != 'POST' or not request.user.is_jobseeker:
        return JsonResponse({'ok': False, 'error': 'Bad request'}, status=400)
    try:
        profile = request.user.jobseeker_profile
    except JobseekerProfile.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Profile not found'}, status=404)

    image = request.FILES.get('image')
    if not image:
        return JsonResponse({'ok': False, 'error': 'No image provided'}, status=400)
    if image.size > 5 * 1024 * 1024:
        return JsonResponse({'ok': False, 'error': 'Image must be under 5 MB'}, status=400)

    # Replace any existing picture
    if profile.profile_picture:
        profile.profile_picture.delete(save=False)
    profile.profile_picture = image
    profile.save(update_fields=['profile_picture', 'updated_at'])
    return JsonResponse({'ok': True, 'url': profile.profile_picture.url})


@login_required
def profile_picture_remove(request):
    if request.method != 'POST' or not request.user.is_jobseeker:
        return JsonResponse({'ok': False, 'error': 'Bad request'}, status=400)
    try:
        profile = request.user.jobseeker_profile
    except JobseekerProfile.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Profile not found'}, status=404)
    if profile.profile_picture:
        profile.profile_picture.delete(save=False)
        profile.profile_picture = None
        profile.save(update_fields=['profile_picture', 'updated_at'])
    return JsonResponse({'ok': True})


@login_required
def applications(request):
    if not request.user.is_jobseeker:
        return redirect('/employers/dashboard/')

    try:
        profile = request.user.jobseeker_profile
    except JobseekerProfile.DoesNotExist:
        return redirect('/register/info/')

    from apps.jobs.models import Application

    sort = request.GET.get('sort', 'recent')
    search = request.GET.get('q', '').strip()

    qs = Application.objects.filter(jobseeker=profile).select_related(
        'job', 'job__company', 'job__education_requirement', 'job__experience_requirement'
    ).prefetch_related('job__skill_requirements', 'job__certification_requirements')

    if search:
        qs = qs.filter(
            Q(job__title__icontains=search) | Q(job__company__name__icontains=search)
        )

    if sort == 'oldest':
        qs = qs.order_by('created_at')
    elif sort == 'status':
        qs = qs.order_by('status', '-created_at')
    else:  # recent
        qs = qs.order_by('-created_at')

    # Compute match score for each application
    items = []
    if profile.profile_complete:
        from apps.matching.engine import compute_match_score
        for app in qs:
            score_data = compute_match_score(app.job, profile)
            items.append({'app': app, 'score': score_data['total']})
    else:
        for app in qs:
            items.append({'app': app, 'score': None})

    return render(request, 'jobseekers/applications.html', {
        'profile': profile,
        'items': items,
        'sort': sort,
        'search': search,
        'unread_notifications': False,
        'unread_messages': False,
    })


def _compute_auto_sectors(profile, education_qs):
    """Return a list of sector codes that should be auto-applied based on profile data."""
    from datetime import date as date_cls
    codes = []
    today = date_cls.today()

    # Senior Citizen — age 60+
    if profile.date_of_birth:
        age = (today.year - profile.date_of_birth.year
               - ((today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)))
        if age >= 60:
            codes.append('senior_citizen')

    # TESDA Graduate — any vocational education entry
    if any(e.level == 'vocational' for e in education_qs):
        codes.append('tesda_graduate')

    # Fresh Graduate — graduated (year_ended) within the last 6 months
    # Since only year is stored, assume December graduation (most conservative estimate)
    threshold = today.year * 12 + today.month - 6  # months since year 0
    for edu in education_qs:
        if not edu.is_current and edu.year_ended:
            grad_months = edu.year_ended * 12 + 12  # December of graduation year
            if grad_months >= threshold:
                codes.append('fresh_graduate')
                break

    return codes


@login_required
def resume(request):
    if not request.user.is_jobseeker:
        return redirect('/employers/dashboard/')

    try:
        profile = request.user.jobseeker_profile
    except JobseekerProfile.DoesNotExist:
        return redirect('/register/info/')

    if request.method == 'POST':
        profile.job_search_query = request.POST.get('job_search_query', '')
        profile.house_unit = request.POST.get('house_unit', '')
        profile.street_barangay = request.POST.get('street_barangay', '')
        profile.province = 'Iloilo'
        profile.province_code = '063000000'

        city_code = request.POST.get('city_municipality', '')
        profile.city_code = city_code

        from apps.core.models import CityMunicipality, Barangay
        try:
            profile.city_municipality = CityMunicipality.objects.get(code=city_code).name
        except CityMunicipality.DoesNotExist:
            profile.city_municipality = ''

        barangay_code = request.POST.get('barangay', '')
        profile.barangay_code = barangay_code
        try:
            profile.barangay = Barangay.objects.get(code=barangay_code).name
        except Barangay.DoesNotExist:
            profile.barangay = ''

        profile.phone = request.POST.get('phone', '')
        profile.contact_email = request.POST.get('contact_email', '')
        profile.bio = request.POST.get('bio', '')
        profile.save()

        # Education
        Education.objects.filter(profile=profile).delete()
        levels = request.POST.getlist('edu_level')
        courses = request.POST.getlist('edu_course')
        institutions = request.POST.getlist('edu_institution')
        starts = request.POST.getlist('edu_start')
        ends = request.POST.getlist('edu_end')
        is_currents = request.POST.getlist('edu_is_current')
        for i, level in enumerate(levels):
            if not level:
                continue
            s = starts[i] if i < len(starts) else ''
            e = ends[i]   if i < len(ends)   else ''
            Education.objects.create(
                profile=profile,
                level=level,
                course_degree=courses[i] if i < len(courses) else '',
                institution=institutions[i] if i < len(institutions) else '',
                year_started=int(s) if s else None,
                year_ended=int(e) if e else None,
                is_current=str(i) in is_currents,
            )

        # Certifications
        Certification.objects.filter(profile=profile).delete()
        cert_names = request.POST.getlist('cert_name')
        cert_orgs = request.POST.getlist('cert_org')
        cert_years = request.POST.getlist('cert_year')
        for i, name in enumerate(cert_names):
            if not name:
                continue
            Certification.objects.create(
                profile=profile,
                name=name,
                issuing_org=cert_orgs[i] if i < len(cert_orgs) else '',
                year_received=cert_years[i] if i < len(cert_years) and cert_years[i] else None,
            )

        # Skills
        Skill.objects.filter(profile=profile).delete()
        for name in request.POST.getlist('skill_name'):
            if name:
                Skill.objects.create(profile=profile, name=name)

        # Work Experience — duration comes as YYYY-MM from type="month" inputs
        WorkExperience.objects.filter(profile=profile).delete()
        positions        = request.POST.getlist('exp_position')
        descriptions     = request.POST.getlist('exp_description')
        companies        = request.POST.getlist('exp_company')
        start_month_years = request.POST.getlist('exp_start_month_year')
        end_month_years   = request.POST.getlist('exp_end_month_year')
        exp_is_currents  = request.POST.getlist('exp_is_current')

        def _split_month_year(val):
            if val and '-' in val:
                parts = val.split('-')
                return parts[1].lstrip('0') or '0', parts[0]
            return '', None

        for i, position in enumerate(positions):
            if not position:
                continue
            start_val = start_month_years[i] if i < len(start_month_years) else ''
            end_val   = end_month_years[i]   if i < len(end_month_years)   else ''
            s_month, s_year = _split_month_year(start_val)
            e_month, e_year = _split_month_year(end_val)
            is_current = str(i) in exp_is_currents
            WorkExperience.objects.create(
                profile=profile,
                position=position,
                company=companies[i] if i < len(companies) else '',
                description=descriptions[i] if i < len(descriptions) else '',
                month_started=s_month,
                year_started=int(s_year) if s_year else None,
                month_ended=e_month if not is_current else '',
                year_ended=int(e_year) if e_year and not is_current else None,
                is_current=is_current,
            )

        # Sectors: manual (user-chosen) + auto-computed
        manual_ids = set(request.POST.getlist('sectors'))
        auto_codes = _compute_auto_sectors(profile, Education.objects.filter(profile=profile))
        auto_ids = set(str(s.id) for s in Sector.objects.filter(code__in=auto_codes))

        profile.sectors.clear()
        profile.sectors.set(manual_ids | auto_ids)
        profile.sector_badge_visibility = request.POST.get('sector_badge_visibility', 'public')
        profile.profile_complete = True
        profile.save()

        return redirect('/dashboard/')

    education    = Education.objects.filter(profile=profile)
    skills       = Skill.objects.filter(profile=profile)
    certifications = Certification.objects.filter(profile=profile)
    experiences  = WorkExperience.objects.filter(profile=profile)

    MANUAL_CODES = ['osy', 'solo_parent', 'pwd', 'lgbtqia']
    manual_sectors = Sector.objects.filter(code__in=MANUAL_CODES)
    auto_codes     = _compute_auto_sectors(profile, education)
    auto_sectors   = Sector.objects.filter(code__in=auto_codes)

    return render(request, 'jobseekers/resume.html', {
        'profile': profile,
        'education': education,
        'skills': skills,
        'certifications': certifications,
        'experiences': experiences,
        'manual_sectors': manual_sectors,
        'auto_sectors': auto_sectors,
        'year_range': range(datetime.now().year, 1949, -1),
        'unread_notifications': False,
        'unread_messages': False,
    })


@login_required
def recommended_jobs(request):
    if not request.user.is_jobseeker:
        return redirect('/employers/dashboard/')

    try:
        profile = request.user.jobseeker_profile
    except Exception:
        return redirect('/register/info/')

    from apps.matching.engine import get_ranked_jobs
    from apps.jobseekers.models import JobInteraction

    tab = request.GET.get('tab', 'for_you')
    sort = request.GET.get('sort', 'match')
    search = request.GET.get('q', '').strip()

    liked_ids = set(JobInteraction.objects.filter(
        jobseeker=profile, interaction_type=JobInteraction.LIKED
    ).values_list('job_id', flat=True))

    hidden_ids = set(JobInteraction.objects.filter(
        jobseeker=profile, interaction_type=JobInteraction.HIDDEN
    ).values_list('job_id', flat=True))

    def apply_search(qs):
        if search:
            return qs.filter(
                Q(title__icontains=search) | Q(company__name__icontains=search)
            )
        return qs

    def apply_sort_qs(qs):
        if sort == 'date_new':
            return qs.order_by('-created_at')
        elif sort == 'date_old':
            return qs.order_by('created_at')
        return qs.order_by('-created_at')

    base_qs = JobPosting.objects.select_related(
        'company', 'education_requirement', 'experience_requirement'
    ).prefetch_related('skill_requirements', 'certification_requirements')

    if tab == 'liked':
        jobs_qs = apply_sort_qs(apply_search(base_qs.filter(id__in=liked_ids, status='open')))
        if profile.profile_complete:
            from apps.matching.engine import compute_match_score
            ranked_jobs = []
            for job in jobs_qs:
                score_data = compute_match_score(job, profile)
                ranked_jobs.append({
                    'job': job,
                    'score': score_data['total'],
                    'breakdown': score_data['breakdown'],
                })
        else:
            ranked_jobs = [{'job': job, 'score': None, 'breakdown': None} for job in jobs_qs]

    elif tab == 'hidden':
        jobs_qs = apply_sort_qs(apply_search(base_qs.filter(id__in=hidden_ids, status='open')))
        if profile.profile_complete:
            from apps.matching.engine import compute_match_score
            ranked_jobs = []
            for job in jobs_qs:
                score_data = compute_match_score(job, profile)
                ranked_jobs.append({
                    'job': job,
                    'score': score_data['total'],
                    'breakdown': score_data['breakdown'],
                })
        else:
            ranked_jobs = [{'job': job, 'score': None, 'breakdown': None} for job in jobs_qs]

    else:
        if profile.profile_complete:
            ranked_jobs = get_ranked_jobs(profile)
            ranked_jobs = [r for r in ranked_jobs if r['job'].id not in hidden_ids]

            if search:
                ranked_jobs = [
                    r for r in ranked_jobs
                    if search.lower() in r['job'].title.lower()
                    or search.lower() in r['job'].company.name.lower()
                ]

            if sort == 'date_new':
                ranked_jobs.sort(key=lambda x: x['job'].created_at, reverse=True)
            elif sort == 'date_old':
                ranked_jobs.sort(key=lambda x: x['job'].created_at)
            elif sort == 'nearest':
                ranked_jobs.sort(
                    key=lambda x: 0 if x['job'].city.lower() == profile.city_municipality.lower() else 1
                )
        else:
            ranked_jobs = []

    jobs_json = []
    posted_map = {}
    for item in ranked_jobs:
        job = item['job']

        edu = None
        try:
            edu = job.education_requirement.get_level_display()
            if job.education_requirement.course_degree:
                edu += f' — {job.education_requirement.course_degree}'
        except Exception:
            pass

        exp = None
        try:
            exp = job.experience_requirement.years_required
        except Exception:
            pass

        jobs_json.append({
            'id': job.id,
            'title': job.title,
            'company': job.company.name,
            'location': job.location_display,
            'description': job.description,
            'score': item['score'],
            'slots': job.slots,
            'education': edu,
            'experience': exp,
            'skills': [s.name for s in job.skill_requirements.all()],
            'certs': [c.name for c in job.certification_requirements.all()],
            'liked': job.id in liked_ids,
            'hidden': job.id in hidden_ids,
        })
        posted_map[str(job.id)] = job.created_at.strftime('%Y-%m-%dT%H:%M:%SZ')

    return render(request, 'jobseekers/recommended_jobs.html', {
        'profile': profile,
        'ranked_jobs': ranked_jobs,
        'liked_ids': liked_ids,
        'hidden_ids': hidden_ids,
        'tab': tab,
        'sort': sort,
        'search': search,
        'jobs_json': json.dumps(jobs_json),
        'posted_map': json.dumps(posted_map),
        'unread_notifications': False,
        'unread_messages': False,
    })


@login_required
def job_like(request, job_id):
    if request.method != 'POST':
        return redirect('/jobs/for-you/')
    from apps.jobseekers.models import JobInteraction
    profile = request.user.jobseeker_profile
    job = get_object_or_404(JobPosting, id=job_id)

    existing = JobInteraction.objects.filter(jobseeker=profile, job=job).first()
    if existing:
        if existing.interaction_type == JobInteraction.LIKED:
            existing.delete()
        else:
            existing.interaction_type = JobInteraction.LIKED
            existing.save()
            from apps.notifications.utils import notify_jobseeker_liked_job
            notify_jobseeker_liked_job(profile, job)
    else:
        JobInteraction.objects.create(
            jobseeker=profile,
            job=job,
            interaction_type=JobInteraction.LIKED
        )
        from apps.notifications.utils import notify_jobseeker_liked_job
        notify_jobseeker_liked_job(profile, job)

    return redirect(request.POST.get('next', '/jobs/for-you/'))


@login_required
def job_hide(request, job_id):
    if request.method != 'POST':
        return redirect('/jobs/for-you/')
    from apps.jobseekers.models import JobInteraction
    profile = request.user.jobseeker_profile
    job = get_object_or_404(JobPosting, id=job_id)

    existing = JobInteraction.objects.filter(jobseeker=profile, job=job).first()
    if existing:
        if existing.interaction_type == JobInteraction.HIDDEN:
            existing.delete()
        else:
            existing.interaction_type = JobInteraction.HIDDEN
            existing.save()
    else:
        JobInteraction.objects.create(
            jobseeker=profile,
            job=job,
            interaction_type=JobInteraction.HIDDEN
        )

    return redirect(request.POST.get('next', '/jobs/for-you/'))


def autocomplete_skills(request):
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse([], safe=False)

    from apps.jobseekers.models import Skill as JobseekerSkill
    skills = JobseekerSkill.objects.filter(
        name__icontains=query
    ).values_list('name', flat=True).distinct().order_by('name')[:10]

    return JsonResponse(list(skills), safe=False)


def autocomplete_positions(request):
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse([], safe=False)

    positions = JobPosting.objects.filter(
        title__icontains=query, status='open'
    ).values_list('title', flat=True).distinct().order_by('title')[:10]

    static_positions = [
        'Accountant', 'Administrative Assistant', 'Architect', 'Bookkeeper',
        'Call Center Agent', 'Cashier', 'Civil Engineer', 'Computer Technician',
        'Construction Worker', 'Cook', 'Customer Service Representative',
        'Data Analyst', 'Data Entry Clerk', 'Delivery Driver', 'Dentist',
        'Electrical Engineer', 'Electrician', 'Factory Worker', 'Financial Analyst',
        'Graphic Designer', 'HR Assistant', 'IT Support', 'Janitor',
        'Logistics Coordinator', 'Marketing Assistant', 'Mechanic', 'Medical Technologist',
        'Midwife', 'Nurse', 'Office Staff', 'Pharmacist', 'Physical Therapist',
        'Plumber', 'Project Manager', 'Purchasing Officer', 'Receptionist',
        'Sales Associate', 'Secretary', 'Security Guard', 'Social Worker',
        'Software Developer', 'Teacher', 'Technician', 'Waiter/Waitress',
        'Web Developer', 'Welder',
    ]

    filtered_static = [p for p in static_positions if query.lower() in p.lower()]
    combined = list(dict.fromkeys(list(positions) + filtered_static))[:10]
    return JsonResponse(combined, safe=False)


def autocomplete_degrees(request):
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse([], safe=False)

    degrees = [
        'BS Accountancy', 'BS Architecture', 'BS Biology', 'BS Business Administration',
        'BS Chemical Engineering', 'BS Chemistry', 'BS Civil Engineering',
        'BS Computer Engineering', 'BS Computer Science', 'BS Criminology',
        'BS Electrical Engineering', 'BS Electronics Engineering', 'BS Environmental Science',
        'BS Finance', 'BS Food Technology', 'BS Forensic Science',
        'BS Hotel and Restaurant Management', 'BS Industrial Engineering',
        'BS Information Systems', 'BS Information Technology', 'BS Interior Design',
        'BS Management Accounting', 'BS Marine Engineering', 'BS Marine Transportation',
        'BS Marketing Management', 'BS Mathematics', 'BS Mechanical Engineering',
        'BS Medical Laboratory Science', 'BS Midwifery', 'BS Mining Engineering',
        'BS Nursing', 'BS Nutrition and Dietetics', 'BS Occupational Therapy',
        'BS Pharmacy', 'BS Physical Therapy', 'BS Psychology', 'BS Radiologic Technology',
        'BS Real Estate Management', 'BS Social Work', 'BS Statistics',
        'BS Tourism Management',
        'AB Communication', 'AB Economics', 'AB English', 'AB Filipino',
        'AB History', 'AB Journalism', 'AB Political Science', 'AB Psychology',
        'AB Sociology',
        'Bachelor of Elementary Education', 'Bachelor of Secondary Education',
        'Bachelor of Physical Education', 'Bachelor of Special Needs Education',
        'Bachelor of Laws', 'Bachelor of Arts in Music', 'Bachelor of Fine Arts',
        'Doctor of Medicine', 'Doctor of Dental Medicine',
        'Automotive Servicing NC II', 'Bookkeeping NC III', 'Computer Hardware Servicing NC II',
        'Cookery NC II', 'Electrical Installation and Maintenance NC II',
        'Food and Beverage Services NC II', 'Housekeeping NC II',
        'Shielded Metal Arc Welding NC II', 'Driving NC II',
        'ABM', 'HUMSS', 'STEM', 'GAS', 'TVL', 'Sports Track', 'Arts and Design Track',
    ]

    filtered = [d for d in degrees if query.lower() in d.lower()][:10]
    return JsonResponse(filtered, safe=False)


def autocomplete_certifications(request):
    query = request.GET.get('q', '').strip()
    if not query or len(query) < 2:
        return JsonResponse([], safe=False)

    from apps.jobseekers.models import Certification as JobseekerCert
    existing = JobseekerCert.objects.filter(
        name__icontains=query
    ).values_list('name', flat=True).distinct().order_by('name')[:10]

    static_certs = [
        'TESDA NC I', 'TESDA NC II', 'TESDA NC III', 'TESDA NC IV',
        'PRC Board Exam - Nursing', 'PRC Board Exam - Medicine',
        'PRC Board Exam - Accountancy', 'PRC Board Exam - Engineering',
        'PRC Board Exam - Pharmacy', 'PRC Board Exam - Physical Therapy',
        'PRC Board Exam - Medical Technology', 'PRC Board Exam - Dentistry',
        'PRC Board Exam - Psychology', 'PRC Board Exam - Social Work',
        'AWS Certified Cloud Practitioner', 'AWS Certified Solutions Architect',
        'Google IT Support Certificate', 'Google Data Analytics Certificate',
        'Microsoft Certified: Azure Fundamentals', 'Cisco CCNA',
        'CompTIA A+', 'CompTIA Security+', 'Oracle Java Certification',
        'Civil Service Eligibility - Professional', 'Civil Service Eligibility - Sub-Professional',
        'First Aid and Basic Life Support', 'BOSH Training Certificate',
        'Occupational Health and Safety', 'Food Safety Certificate',
        'NCII Cookery', 'NCII Welding', 'NCII Electrical',
    ]

    filtered_static = [c for c in static_certs if query.lower() in c.lower()]
    combined = list(dict.fromkeys(list(existing) + filtered_static))[:10]
    return JsonResponse(combined, safe=False)