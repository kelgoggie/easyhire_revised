from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from apps.core.hashids import encode as _hashid
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
def job_apply(request, job_id):
    """Create an Application for the logged-in jobseeker on the given job."""
    if request.method != 'POST' or not request.user.is_jobseeker:
        return redirect(f'/jobs/view/{_hashid(job_id)}/')
    try:
        profile = request.user.jobseeker_profile
    except JobseekerProfile.DoesNotExist:
        return redirect('/register/info/')

    from apps.jobs.models import Application
    job = get_object_or_404(JobPosting, id=job_id, status='open')
    message = (request.POST.get('message') or '').strip()
    app, created = Application.objects.get_or_create(
        jobseeker=profile, job=job,
        defaults={'message': message},
    )
    if not created and message and not app.message:
        app.message = message
        app.save(update_fields=['message'])

    # Notify every company representative when a new application comes in
    # (no notification on subsequent re-submits — only on create).
    if created:
        from apps.notifications.models import Notification
        for rep in job.company.representatives.select_related('user').all():
            Notification.objects.create(
                recipient=rep.user,
                notif_type=Notification.NEW_APPLICATION,
                company=job.company,
                jobseeker=profile,
                job=job,
            )

    return redirect('/applications/')


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
        # Log the technical details for ops but show users a friendly message.
        print(f'[resume_parser] {type(e).__name__}: {e}')
        return JsonResponse({
            'ok': False,
            'error': "We couldn't read that PDF. Try a text-based PDF (not a photo or scan), or fill in your resume manually.",
        }, status=400)

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


# Allowed value sets for the privacy radios (kept here so the template and view agree).
# Stored in CharField(max_length=10) so keep these short.
# profile_visibility:  'public' = keep visible after hire, 'hidden' = hide after hire
# sector_badge_visibility: 'public' = all employers, 'similar' = only employers with similar badges, 'hidden' = no employers
PROFILE_VISIBILITY_VALUES      = {'public', 'hidden'}
SECTOR_BADGE_VISIBILITY_VALUES = {'public', 'similar', 'hidden'}

# Philippine government / school IDs offered when requesting a personal-info change.
VALID_PH_IDS = [
    'PhilSys (National ID)',
    'Philippine Passport',
    "Driver's License",
    'UMID (Unified Multi-Purpose ID)',
    'SSS ID',
    'GSIS eCard',
    'PRC ID',
    'Postal ID',
    "Voter's ID / Voter's Certification",
    'School ID',
    'PSA Birth Certificate',
    'TIN ID',
    'PhilHealth ID',
    'Senior Citizen ID',
    'PWD ID',
    'Pag-IBIG Loyalty Card Plus',
    'OFW iDOLE Card',
]


@login_required
def settings_view(request):
    if not request.user.is_jobseeker:
        return redirect('/employers/dashboard/')
    try:
        profile = request.user.jobseeker_profile
    except JobseekerProfile.DoesNotExist:
        return redirect('/register/info/')

    from apps.jobseekers.models import PersonalInfoChangeRequest
    pending_change = PersonalInfoChangeRequest.objects.filter(
        profile=profile, status=PersonalInfoChangeRequest.STATUS_PENDING
    ).first()

    saved_section = None

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'personal_change' and not pending_change:
            id_doc = request.FILES.get('id_document')
            if id_doc and id_doc.size <= 10 * 1024 * 1024:
                dob = profile.date_of_birth
                dob_raw = request.POST.get('date_of_birth', '').strip()
                if dob_raw:
                    for fmt in ('%m/%d/%Y', '%B %d, %Y'):
                        try:
                            dob = datetime.strptime(dob_raw, fmt).date()
                            break
                        except ValueError:
                            continue
                sex = request.POST.get('sex', '').strip()
                if sex not in {'M', 'F'}:
                    sex = profile.sex
                PersonalInfoChangeRequest.objects.create(
                    profile=profile,
                    first_name  = (request.POST.get('first_name')  or profile.first_name).strip(),
                    middle_name = (request.POST.get('middle_name') or '').strip(),
                    last_name   = (request.POST.get('last_name')   or profile.last_name).strip(),
                    suffix      = (request.POST.get('suffix')      or '').strip(),
                    date_of_birth = dob,
                    sex         = sex,
                    id_document = id_doc,
                )
                return redirect('/settings/')

        elif form_type == 'privacy':
            pv = request.POST.get('profile_visibility', '').strip()
            bv = request.POST.get('sector_badge_visibility', '').strip()
            updates = {}
            if pv in PROFILE_VISIBILITY_VALUES:
                updates['profile_visibility'] = pv
            if bv in SECTOR_BADGE_VISIBILITY_VALUES:
                updates['sector_badge_visibility'] = bv
            if updates:
                for k, v in updates.items():
                    setattr(profile, k, v)
                profile.save(update_fields=list(updates.keys()))
            if _is_ajax(request):
                return JsonResponse({'ok': True, **updates})
            saved_section = 'privacy'

    return render(request, 'jobseekers/settings.html', {
        'profile': profile,
        'pending_change': pending_change,
        'saved_section': saved_section,
        'valid_ph_ids': VALID_PH_IDS,
    })


@login_required
def change_password(request):
    if request.method != 'POST':
        return redirect('/settings/')
    from django.contrib.auth import update_session_auth_hash
    user = request.user
    current = request.POST.get('current_password', '')
    new1    = request.POST.get('new_password', '')
    new2    = request.POST.get('confirm_password', '')

    if not user.check_password(current):
        return JsonResponse({'ok': False, 'error': 'Current password is incorrect.'}, status=400)
    if len(new1) < 8:
        return JsonResponse({'ok': False, 'error': 'New password must be at least 8 characters.'}, status=400)
    if new1 != new2:
        return JsonResponse({'ok': False, 'error': "New passwords don't match."}, status=400)
    if new1 == current:
        return JsonResponse({'ok': False, 'error': 'New password must differ from current.'}, status=400)

    user.set_password(new1)
    user.save(update_fields=['password'])
    update_session_auth_hash(request, user)
    return JsonResponse({'ok': True})


@login_required
def companies_list(request):
    """Jobseeker-facing browse-all-companies page."""
    from django.db.models import Count, Q as DjQ
    from apps.employers.models import Company
    from apps.jobs.models import JobPosting
    from apps.core.pagination import paginate, querystring_without

    search = request.GET.get('q', '').strip()
    sort = request.GET.get('sort', 'name')

    qs = Company.objects.filter(verification_status=Company.VERIFIED)

    if search:
        qs = qs.filter(name__icontains=search)

    qs = qs.annotate(
        open_jobs_count=Count('job_postings',
                              filter=DjQ(job_postings__status=JobPosting.STATUS_OPEN)),
    )

    if sort == 'jobs':
        qs = qs.order_by('-open_jobs_count', 'name')
    else:  # 'name'
        qs = qs.order_by('name')

    # Companies the current jobseeker already follows (for filled-vs-empty heart)
    followed_ids = set()
    try:
        profile = request.user.jobseeker_profile
        followed_ids = set(profile.followed_companies.values_list('id', flat=True))
    except Exception:
        pass

    total = qs.count()
    page = paginate(request, qs, per_page=12)

    return render(request, 'jobseekers/companies_list.html', {
        'companies': list(page.object_list),
        'total': total,
        'search': search,
        'sort': sort,
        'followed_ids': followed_ids,
        'page': page,
        'qs_base': querystring_without(request, 'page'),
        'unread_notifications': False,
        'unread_messages': False,
    })


@login_required
def company_public(request, pk):
    """Jobseeker-facing read-only company profile (mirrors employer-side layout)."""
    from django.db.models import Count, Q as DjQ
    from apps.employers.models import Company
    company = get_object_or_404(Company, pk=pk)

    jobs = (
        JobPosting.objects.filter(company=company, status=JobPosting.STATUS_OPEN)
        .annotate(
            liked_by_count=Count(
                'jobseeker_interactions',
                filter=DjQ(jobseeker_interactions__interaction_type='liked'),
                distinct=True,
            ),
        )
        .select_related('experience_requirement')
        .prefetch_related('skill_requirements', 'certification_requirements', 'education_requirements')
        .order_by('-created_at')
    )
    followers_count = company.followers.count() if hasattr(company, 'followers') else 0

    is_following = False
    rep_phone = ''
    try:
        if request.user.is_jobseeker:
            is_following = request.user.jobseeker_profile.followed_companies.filter(pk=company.pk).exists()
    except Exception:
        pass
    rep = company.representatives.first()
    if rep:
        rep_phone = getattr(rep, 'phone', '') or ''

    return render(request, 'jobseekers/company_public.html', {
        'company': company,
        'jobs': jobs,
        'followers_count': followers_count,
        'is_following': is_following,
        'rep_phone': rep_phone,
    })


@login_required
def follow_company(request, pk):
    if request.method != 'POST' or not request.user.is_jobseeker:
        return JsonResponse({'ok': False}, status=400)
    from apps.employers.models import Company
    company = get_object_or_404(Company, pk=pk)
    profile = request.user.jobseeker_profile
    if profile.followed_companies.filter(pk=company.pk).exists():
        profile.followed_companies.remove(company)
        following = False
    else:
        profile.followed_companies.add(company)
        following = True
    followers_count = company.followers.count() if hasattr(company, 'followers') else 0
    return JsonResponse({'ok': True, 'following': following, 'followers_count': followers_count})


@login_required
def deactivate_account(request):
    if request.method != 'POST':
        return redirect('/settings/')
    from django.contrib.auth import logout
    password = request.POST.get('confirm_password') or ''
    if not request.user.check_password(password):
        return JsonResponse({'ok': False, 'error': "Password is incorrect."}, status=400)

    user = request.user
    user.is_active = False
    user.save(update_fields=['is_active'])
    logout(request)
    return JsonResponse({'ok': True, 'redirect': '/'})


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
        'job', 'job__company', 'job__experience_requirement'
    ).prefetch_related('job__skill_requirements', 'job__certification_requirements', 'job__education_requirements')

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

    from apps.core.pagination import paginate, querystring_without
    page = paginate(request, items, per_page=10)

    return render(request, 'jobseekers/applications.html', {
        'profile': profile,
        'items': list(page.object_list),
        'sort': sort,
        'search': search,
        'page': page,
        'qs_base': querystring_without(request, 'page'),
        'unread_notifications': False,
        'unread_messages': False,
    })


def _compute_auto_sectors(profile, education_qs):
    """Return a list of sector codes that should be auto-applied based on profile data.

    Rules:
      - senior_citizen : age >= 60 (computed from date_of_birth)
      - tesda_graduate : any Education entry with level == 'vocational'
      - fresh_graduate : graduated within the last 24 months AND no work experience
    """
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

    # Fresh Graduate — graduated within the last 24 months AND no work experience.
    # Year is the only granularity we store, so assume December graduation.
    has_work_experience = WorkExperience.objects.filter(profile=profile).exists()
    if not has_work_experience:
        threshold = today.year * 12 + today.month - 24  # months since year 0
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

    base_qs = JobPosting.objects.select_related(
        'company', 'experience_requirement'
    ).prefetch_related('skill_requirements', 'certification_requirements', 'education_requirements')

    def _apply_sort(items):
        """Sort the ranked-jobs list in-place by the active `sort` key."""
        if sort == 'date_new':
            items.sort(key=lambda x: x['job'].created_at, reverse=True)
        elif sort == 'date_old':
            items.sort(key=lambda x: x['job'].created_at)
        elif sort == 'nearest':
            from apps.matching.engine import score_location
            # Higher score_location → physically closer → sort first.
            items.sort(key=lambda x: -score_location(x['job'], profile))
        elif sort == 'match':
            items.sort(key=lambda x: -(x['score'] or 0))
        return items

    def _build_ranked(jobs_qs):
        if profile.profile_complete:
            from apps.matching.engine import compute_match_score
            return [
                {'job': job, 'score': (sd := compute_match_score(job, profile))['total'], 'breakdown': sd['breakdown']}
                for job in jobs_qs
            ]
        return [{'job': job, 'score': None, 'breakdown': None} for job in jobs_qs]

    if tab == 'liked':
        jobs_qs = apply_search(base_qs.filter(id__in=liked_ids, status='open'))
        ranked_jobs = _apply_sort(_build_ranked(jobs_qs))

    elif tab == 'hidden':
        jobs_qs = apply_search(base_qs.filter(id__in=hidden_ids, status='open'))
        ranked_jobs = _apply_sort(_build_ranked(jobs_qs))

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
            _apply_sort(ranked_jobs)
        else:
            ranked_jobs = []

    # Match score is internal — never filter cards out based on it. Sorting still
    # puts strongest matches first via the engine's ranking.
    from apps.core.pagination import paginate, querystring_without
    page = paginate(request, ranked_jobs, per_page=12)
    page_items = list(page.object_list)

    jobs_json = []
    posted_map = {}
    for item in page_items:
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

    context = {
        'profile': profile,
        'ranked_jobs': page_items,
        'liked_ids': liked_ids,
        'hidden_ids': hidden_ids,
        'tab': tab,
        'sort': sort,
        'search': search,
        'jobs_json': jobs_json,
        'posted_map': posted_map,
        'page': page,
        'qs_base': querystring_without(request, 'page'),
        'unread_notifications': False,
        'unread_messages': False,
    }

    if _is_ajax(request):
        from django.template.loader import render_to_string
        html = render_to_string('jobseekers/_jobs_results.html', context, request=request)
        return JsonResponse({
            'html': html,
            'jobs_json': jobs_json,
            'posted_map': posted_map,
            'tab': tab,
        })

    return render(request, 'jobseekers/recommended_jobs.html', context)


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


@login_required
def job_like(request, job_id):
    if request.method != 'POST':
        return redirect('/jobs/for-you/')
    from apps.jobseekers.models import JobInteraction
    from apps.notifications.utils import refresh_jobseeker_liked_job_notification
    profile = request.user.jobseeker_profile
    job = get_object_or_404(JobPosting, id=job_id)

    existing = JobInteraction.objects.filter(jobseeker=profile, job=job).first()
    if existing and existing.interaction_type == JobInteraction.LIKED:
        existing.delete()
        liked = False
    else:
        if existing:
            existing.interaction_type = JobInteraction.LIKED
            existing.save(update_fields=['interaction_type'])
        else:
            JobInteraction.objects.create(jobseeker=profile, job=job, interaction_type=JobInteraction.LIKED)
        liked = True

    refresh_jobseeker_liked_job_notification(job)

    if _is_ajax(request):
        return JsonResponse({'ok': True, 'liked': liked})
    return redirect(request.POST.get('next', '/jobs/for-you/'))


@login_required
def job_hide(request, job_id):
    if request.method != 'POST':
        return redirect('/jobs/for-you/')
    from apps.jobseekers.models import JobInteraction
    profile = request.user.jobseeker_profile
    job = get_object_or_404(JobPosting, id=job_id)

    existing = JobInteraction.objects.filter(jobseeker=profile, job=job).first()
    if existing and existing.interaction_type == JobInteraction.HIDDEN:
        existing.delete()
        hidden = False
    else:
        if existing:
            existing.interaction_type = JobInteraction.HIDDEN
            existing.save(update_fields=['interaction_type'])
        else:
            JobInteraction.objects.create(jobseeker=profile, job=job, interaction_type=JobInteraction.HIDDEN)
        hidden = True

    if _is_ajax(request):
        return JsonResponse({'ok': True, 'hidden': hidden})
    return redirect(request.POST.get('next', '/jobs/for-you/'))


# ─── Static vocabularies for NLP-powered autocomplete ────────────────────
# These give new users useful suggestions even before any other user has
# typed similar things. The user's DB entries are merged in at runtime.

STATIC_SKILLS = [
    # Programming languages
    'Python', 'JavaScript', 'TypeScript', 'Java', 'C', 'C++', 'C#', 'PHP',
    'Ruby', 'Go', 'Rust', 'Kotlin', 'Swift', 'SQL', 'HTML', 'CSS', 'R',
    'Scala', 'Perl', 'Dart', 'Lua', 'MATLAB', 'VBA',
    # Web / frameworks
    'React', 'Vue.js', 'Angular', 'Next.js', 'Nuxt.js', 'Svelte',
    'Node.js', 'Django', 'Flask', 'FastAPI', 'Laravel', 'CodeIgniter',
    'Spring Boot', 'Express.js', 'jQuery', 'Tailwind CSS', 'Bootstrap',
    'WordPress', 'Shopify', 'Webflow', 'GraphQL', 'REST APIs',
    # Mobile
    'React Native', 'Flutter', 'Android Development', 'iOS Development',
    # Data / DB
    'MySQL', 'PostgreSQL', 'MongoDB', 'SQLite', 'Redis', 'Oracle Database',
    'Microsoft SQL Server', 'Firebase', 'Supabase', 'Elasticsearch',
    'Excel', 'Advanced Excel', 'Power BI', 'Tableau', 'Looker', 'Google Sheets',
    'Data Analysis', 'Data Visualization', 'Data Cleaning', 'ETL',
    'Machine Learning', 'Deep Learning', 'Natural Language Processing',
    'Statistics', 'Predictive Modeling', 'A/B Testing', 'pandas', 'NumPy',
    'scikit-learn', 'TensorFlow', 'PyTorch',
    # DevOps / cloud
    'Git', 'GitHub', 'GitLab', 'Bitbucket', 'Docker', 'Kubernetes',
    'AWS', 'Azure', 'Google Cloud', 'Heroku', 'DigitalOcean', 'Vercel',
    'Linux', 'Ubuntu', 'CentOS', 'Bash', 'PowerShell', 'CI/CD',
    'Jenkins', 'GitHub Actions', 'Terraform', 'Ansible',
    # Cybersecurity / networking
    'Network Administration', 'Cybersecurity', 'Penetration Testing',
    'Information Security', 'Firewall Configuration', 'VPN', 'TCP/IP',
    'Wireshark', 'Vulnerability Assessment', 'Cisco Networking',
    # Design / creative
    'Adobe Photoshop', 'Adobe Illustrator', 'Adobe Premiere Pro',
    'Adobe After Effects', 'Adobe InDesign', 'Adobe XD', 'Adobe Lightroom',
    'Figma', 'Canva', 'Sketch', 'CorelDRAW', 'GIMP', 'Inkscape',
    'AutoCAD', 'SolidWorks', 'SketchUp', 'Revit', 'Blender', '3D Modeling',
    'Video Editing', 'Photography', 'Photo Editing', 'Animation',
    'Graphic Design', 'UI/UX Design', 'Wireframing', 'Prototyping',
    'Logo Design', 'Brand Identity', 'Typography', 'Color Theory',
    # Office / productivity
    'Microsoft Word', 'Microsoft Excel', 'Microsoft PowerPoint',
    'Microsoft Outlook', 'Microsoft Access', 'Microsoft Teams',
    'Google Suite', 'Google Docs', 'Google Sheets', 'Google Slides',
    'Google Calendar', 'Google Drive', 'Slack', 'Trello', 'Notion',
    'Asana', 'Jira', 'ClickUp', 'Monday.com', 'Airtable', 'Zoom',
    # Communication / soft skills
    'Communication', 'Verbal Communication', 'Written Communication',
    'Public Speaking', 'Presentation Skills', 'Leadership', 'Team Leadership',
    'Teamwork', 'Collaboration', 'Problem Solving', 'Critical Thinking',
    'Analytical Thinking', 'Time Management', 'Project Management',
    'Agile Methodology', 'Scrum', 'Kanban', 'Adaptability', 'Flexibility',
    'Customer Service', 'Client Relations', 'Conflict Resolution',
    'Negotiation', 'Persuasion', 'Active Listening', 'Empathy',
    'Decision Making', 'Strategic Planning', 'Creativity', 'Innovation',
    'Attention to Detail', 'Multitasking', 'Work Ethic', 'Self-Motivation',
    'Mentoring', 'Coaching',
    # Language
    'English', 'Filipino', 'Tagalog', 'Hiligaynon (Ilonggo)', 'Kinaray-a',
    'Cebuano', 'Aklanon', 'Bicolano', 'Mandarin', 'Cantonese',
    'Spanish', 'Japanese', 'Korean', 'French', 'German', 'Arabic',
    # Healthcare / clinical
    'Patient Care', 'Patient Assessment', 'First Aid', 'CPR', 'BLS',
    'ACLS', 'Phlebotomy', 'IV Therapy', 'Nursing Care', 'Wound Care',
    'Vital Signs Monitoring', 'Pharmacology', 'Medication Administration',
    'Medical Records', 'EMR Software', 'Clinical Skills', 'Triage',
    'Infection Control', 'Health Education', 'Geriatric Care',
    'Pediatric Care', 'Mental Health Support',
    # Trade / vocational
    'Carpentry', 'Welding (SMAW)', 'Welding (GTAW)', 'Plumbing',
    'Electrical Wiring', 'Electrical Installation', 'Masonry', 'Painting',
    'Construction', 'Tile Setting', 'Roofing', 'Automotive Repair',
    'Motorcycle Repair', 'Diesel Mechanics', 'Aircon Servicing',
    'Refrigeration', 'Driving', 'Defensive Driving',
    'Heavy Equipment Operation', 'Forklift Operation', 'Cooking', 'Baking',
    'Pastry Making', 'Filipino Cuisine', 'Asian Cuisine',
    'Western Cuisine', 'Sewing', 'Tailoring', 'Dressmaking',
    'Bartending', 'Mixology', 'Barista', 'Coffee Making',
    'Housekeeping', 'Laundry', 'Childcare', 'Caregiving',
    'Elder Care', 'Massage Therapy',
    # Business / finance
    'Accounting', 'Bookkeeping', 'Auditing', 'Financial Analysis',
    'Financial Reporting', 'Budgeting', 'Forecasting', 'Cost Accounting',
    'Payroll', 'Tax Preparation', 'Tax Compliance', 'BIR Filing',
    'Sales', 'B2B Sales', 'B2C Sales', 'Retail Sales', 'Lead Generation',
    'Cold Calling', 'Marketing', 'Brand Management',
    'Digital Marketing', 'SEO', 'SEM', 'Google Ads', 'Facebook Ads',
    'Social Media Management', 'Content Marketing', 'Content Writing',
    'Copywriting', 'Email Marketing', 'CRM', 'Salesforce', 'HubSpot',
    'Market Research', 'Business Development', 'Entrepreneurship',
    # Operations
    'Inventory Management', 'Stock Control', 'Supply Chain', 'Logistics',
    'Procurement', 'Vendor Management', 'Quality Control',
    'Quality Assurance', 'Operations Management', 'Process Improvement',
    'Lean Manufacturing', 'Six Sigma', 'Warehouse Management',
    'Shipping and Receiving',
    # Teaching / training
    'Teaching', 'Tutoring', 'Curriculum Development', 'Lesson Planning',
    'Classroom Management', 'Online Teaching', 'Student Assessment',
    'Educational Technology', 'Training', 'Workshop Facilitation',
    'Employee Onboarding',
    # HR
    'Recruitment', 'Talent Acquisition', 'Interviewing',
    'Performance Management', 'Employee Relations', 'HR Policies',
    'Compensation and Benefits', 'Labor Law Compliance',
    # Customer service / BPO
    'Phone Support', 'Email Support', 'Live Chat Support',
    'Technical Support', 'Customer Retention', 'Account Management',
    'Zendesk', 'Freshdesk',
]

STATIC_POSITIONS = [
    # Admin / clerical
    'Administrative Assistant', 'Office Assistant', 'Office Staff',
    'Executive Assistant', 'Secretary', 'Receptionist', 'Hotel Receptionist',
    'Data Entry Clerk', 'Office Clerk', 'File Clerk', 'Liaison Officer',
    # Finance / accounting
    'Accountant', 'Junior Accountant', 'Senior Accountant', 'Accounting Clerk',
    'Bookkeeper', 'Auditor', 'Internal Auditor', 'Tax Specialist',
    'Financial Analyst', 'Finance Officer', 'Budget Officer',
    'Treasury Officer', 'Cashier', 'Bank Teller', 'Loan Officer',
    'Credit Analyst',
    # Architecture / engineering
    'Architect', 'Junior Architect', 'Civil Engineer', 'Structural Engineer',
    'Mechanical Engineer', 'Electrical Engineer', 'Electronics Engineer',
    'Industrial Engineer', 'Chemical Engineer', 'Mining Engineer',
    'Marine Engineer', 'Project Engineer', 'Site Engineer',
    'Quantity Surveyor', 'Draftsman', 'CAD Operator',
    # IT / Software / data
    'Computer Technician', 'IT Support', 'IT Specialist',
    'Technical Support', 'Help Desk Analyst',
    'Software Developer', 'Software Engineer', 'Junior Developer',
    'Senior Developer', 'Full Stack Developer', 'Frontend Developer',
    'Backend Developer', 'Web Developer', 'Mobile Developer',
    'iOS Developer', 'Android Developer', 'Database Administrator',
    'Network Administrator', 'System Administrator', 'DevOps Engineer',
    'QA Engineer', 'Quality Assurance Tester', 'Data Analyst',
    'Data Scientist', 'Data Engineer', 'Business Analyst',
    'Systems Analyst', 'UI/UX Designer', 'Product Manager',
    'Scrum Master', 'Cybersecurity Analyst',
    # Healthcare / clinical
    'Doctor', 'General Practitioner', 'Resident Physician',
    'Dentist', 'Veterinarian', 'Pharmacist', 'Nurse', 'Staff Nurse',
    'Nursing Assistant', 'Midwife', 'Caregiver', 'Medical Technologist',
    'Radiologic Technologist', 'Physical Therapist', 'Occupational Therapist',
    'Medical Receptionist', 'Medical Records Clerk', 'Phlebotomist',
    'Laboratory Aide',
    # Education
    'Teacher', 'Elementary Teacher', 'High School Teacher',
    'Senior High Teacher', 'College Instructor', 'Professor',
    'Substitute Teacher', 'Tutor', 'Teaching Assistant',
    'Guidance Counselor', 'School Principal', 'Librarian',
    # Sales / marketing
    'Sales Associate', 'Sales Representative', 'Sales Manager',
    'Account Executive', 'Account Manager',
    'Marketing Assistant', 'Marketing Officer', 'Marketing Manager',
    'Digital Marketing Specialist', 'Brand Manager',
    'Social Media Manager', 'Content Creator', 'Content Writer',
    'Copywriter', 'SEO Specialist',
    # Operations / management
    'Operations Manager', 'Operations Supervisor', 'Branch Manager',
    'Store Manager', 'Assistant Manager', 'Team Leader', 'Supervisor',
    'Project Manager', 'Program Manager', 'General Manager',
    'Department Head',
    # HR
    'HR Assistant', 'HR Officer', 'HR Manager', 'HR Generalist',
    'Recruitment Specialist', 'Talent Acquisition Specialist',
    'Training Officer', 'Compensation and Benefits Officer',
    # Logistics / supply chain
    'Logistics Coordinator', 'Logistics Officer', 'Supply Chain Officer',
    'Warehouse Worker', 'Warehouse Supervisor', 'Inventory Clerk',
    'Procurement Officer', 'Purchasing Officer', 'Purchaser',
    'Delivery Driver', 'Truck Driver', 'Dispatcher',
    # Customer service / BPO
    'Customer Service Representative', 'Call Center Agent',
    'Technical Support Representative', 'Chat Support Agent',
    'Virtual Assistant',
    # Trades / blue collar
    'Construction Worker', 'Mason', 'Carpenter', 'Painter', 'Electrician',
    'Plumber', 'Welder', 'Mechanic', 'Automotive Mechanic',
    'Heavy Equipment Operator', 'Forklift Operator', 'Crane Operator',
    'Machine Operator', 'Factory Worker', 'Production Worker',
    'Assembly Line Worker', 'Quality Inspector',
    # Hospitality / food service
    'Chef', 'Sous Chef', 'Cook', 'Line Cook', 'Pastry Chef', 'Baker',
    'Waiter / Waitress', 'Server', 'Busser', 'Bartender', 'Barista',
    'Restaurant Manager', 'Food and Beverage Supervisor',
    'Hotel Manager', 'Concierge', 'Housekeeper',
    # Security / facilities
    'Security Guard', 'Security Officer', 'Janitor', 'Maintenance Worker',
    'Building Maintenance', 'Facilities Coordinator',
    # Creative / media
    'Graphic Designer', 'Illustrator', 'Photographer', 'Videographer',
    'Video Editor', 'Animator', 'Sound Engineer',
    # Legal / public service
    'Lawyer', 'Paralegal', 'Legal Secretary', 'Notary Public',
    'Government Employee', 'Barangay Worker', 'Social Worker',
    'Police Officer', 'Firefighter',
    # Maritime
    'Seafarer', 'Able Seaman', 'Marine Engineer Officer', 'Deck Officer',
    # Agriculture
    'Farmer', 'Agriculturist', 'Fisherman',
]

STATIC_DEGREES = [
    # BS degrees
    'BS Accountancy', 'BS Accounting Information Systems', 'BS Agriculture',
    'BS Agricultural Engineering', 'BS Architecture', 'BS Biology',
    'BS Business Administration', 'BS Business Administration - Marketing',
    'BS Business Administration - Financial Management',
    'BS Business Administration - Human Resource Management',
    'BS Business Administration - Operations Management',
    'BS Chemical Engineering', 'BS Chemistry', 'BS Civil Engineering',
    'BS Computer Engineering', 'BS Computer Science', 'BS Criminology',
    'BS Customs Administration', 'BS Economics',
    'BS Electrical Engineering', 'BS Electronics Engineering',
    'BS Environmental Engineering', 'BS Environmental Science',
    'BS Entrepreneurship', 'BS Finance', 'BS Food Technology',
    'BS Forensic Science', 'BS Geodetic Engineering', 'BS Geology',
    'BS Hospitality Management', 'BS Hotel and Restaurant Management',
    'BS Industrial Engineering', 'BS Information Systems',
    'BS Information Technology', 'BS Interior Design',
    'BS International Studies', 'BS Management Accounting',
    'BS Marine Biology', 'BS Marine Engineering', 'BS Marine Transportation',
    'BS Marketing Management', 'BS Mathematics', 'BS Mechanical Engineering',
    'BS Medical Laboratory Science', 'BS Medical Technology',
    'BS Midwifery', 'BS Mining Engineering', 'BS Nursing',
    'BS Nutrition and Dietetics', 'BS Occupational Therapy',
    'BS Office Administration', 'BS Pharmacy', 'BS Physical Therapy',
    'BS Physics', 'BS Psychology', 'BS Public Administration',
    'BS Radiologic Technology', 'BS Real Estate Management',
    'BS Social Work', 'BS Statistics', 'BS Tourism Management',
    'BS Sports Science', 'BS Veterinary Medicine',
    # AB degrees
    'AB Broadcasting', 'AB Communication', 'AB Communication Arts',
    'AB Economics', 'AB English', 'AB Filipino', 'AB History',
    'AB International Studies', 'AB Journalism', 'AB Mass Communication',
    'AB Multimedia Arts', 'AB Philosophy', 'AB Political Science',
    'AB Psychology', 'AB Public Administration', 'AB Sociology',
    'AB Theology',
    # Education
    'Bachelor of Elementary Education', 'Bachelor of Secondary Education',
    'Bachelor of Secondary Education Major in English',
    'Bachelor of Secondary Education Major in Mathematics',
    'Bachelor of Secondary Education Major in Science',
    'Bachelor of Secondary Education Major in Social Studies',
    'Bachelor of Secondary Education Major in Filipino',
    'Bachelor of Early Childhood Education',
    'Bachelor of Physical Education', 'Bachelor of Special Needs Education',
    'Bachelor of Technical-Vocational Teacher Education',
    # Law / arts / professional
    'Bachelor of Laws', 'Juris Doctor', 'Bachelor of Arts in Music',
    'Bachelor of Music', 'Bachelor of Fine Arts',
    'Bachelor of Library and Information Science',
    'Doctor of Medicine', 'Doctor of Dental Medicine',
    'Doctor of Optometry', 'Doctor of Veterinary Medicine',
    # Master / doctoral
    'Master of Business Administration', 'Master of Public Administration',
    'Master of Arts in Education', 'Master of Engineering',
    'Master of Science in Computer Science',
    'Master of Science in Information Technology',
    'Master of Science in Nursing', 'Master of Laws',
    'Doctor of Philosophy in Education',
    # TESDA / vocational (with NC II/III)
    'Automotive Servicing NC II', 'Automotive Servicing NC III',
    'Bookkeeping NC III', 'Bread and Pastry Production NC II',
    'Caregiving NC II', 'Carpentry NC II',
    'Computer Hardware Servicing NC II', 'Computer Systems Servicing NC II',
    'Cookery NC II', 'Domestic Refrigeration and Air Conditioning NC II',
    'Dressmaking NC II', 'Driving NC II',
    'Electrical Installation and Maintenance NC II',
    'Electronic Products Assembly and Servicing NC II',
    'Events Management Services NC III',
    'Food and Beverage Services NC II', 'Front Office Services NC II',
    'Hairdressing NC II', 'Heavy Equipment Operation NC II',
    'Heavy Equipment Servicing NC III', 'Housekeeping NC II',
    'Masonry NC II', 'Massage Therapy NC II',
    'Motorcycle/Small Engine Servicing NC II',
    'Pharmacy Services NC III', 'Plumbing NC II',
    'Refrigeration and Air Conditioning Servicing NC II',
    'Security Services NC II', 'Shielded Metal Arc Welding NC II',
    'Shielded Metal Arc Welding NC III', 'Tailoring NC II',
    'Tile Setting NC II', 'Trainers Methodology Level I',
    'Visual Graphic Design NC III', 'Welding NC II',
    # SHS strands
    'Senior High - ABM', 'Senior High - HUMSS', 'Senior High - STEM',
    'Senior High - GAS', 'Senior High - TVL', 'Senior High - Sports Track',
    'Senior High - Arts and Design Track',
    'ABM', 'HUMSS', 'STEM', 'GAS', 'TVL',
    # Below college
    'High School Graduate', 'Senior High School Graduate',
    'Elementary Graduate',
]

STATIC_CERTS = [
    # TESDA
    'TESDA NC I', 'TESDA NC II', 'TESDA NC III', 'TESDA NC IV',
    'TESDA Trainers Methodology I', 'TESDA Trainers Methodology II',
    'TESDA Assessor Certification',
    'TESDA Cookery NC II', 'TESDA Bread and Pastry Production NC II',
    'TESDA Food and Beverage Services NC II', 'TESDA Housekeeping NC II',
    'TESDA Bartending NC II', 'TESDA Caregiving NC II',
    'TESDA Computer Systems Servicing NC II',
    'TESDA Computer Hardware Servicing NC II',
    'TESDA Electrical Installation and Maintenance NC II',
    'TESDA Shielded Metal Arc Welding NC II',
    'TESDA Automotive Servicing NC II', 'TESDA Driving NC II',
    'TESDA Heavy Equipment Operation NC II',
    'TESDA Massage Therapy NC II',
    # PRC board exams
    'PRC Board Exam - Nursing', 'PRC Board Exam - Medicine',
    'PRC Board Exam - Dentistry', 'PRC Board Exam - Accountancy',
    'PRC Board Exam - Civil Engineering',
    'PRC Board Exam - Mechanical Engineering',
    'PRC Board Exam - Electrical Engineering',
    'PRC Board Exam - Electronics Engineering',
    'PRC Board Exam - Chemical Engineering',
    'PRC Board Exam - Industrial Engineering',
    'PRC Board Exam - Architecture',
    'PRC Board Exam - Pharmacy', 'PRC Board Exam - Physical Therapy',
    'PRC Board Exam - Occupational Therapy',
    'PRC Board Exam - Medical Technology',
    'PRC Board Exam - Radiologic Technology',
    'PRC Board Exam - Midwifery', 'PRC Board Exam - Psychology',
    'PRC Board Exam - Social Work', 'PRC Board Exam - Criminology',
    'PRC Board Exam - Teaching (LET)', 'PRC Board Exam - Optometry',
    'PRC Board Exam - Veterinary Medicine',
    'PRC Board Exam - Geodetic Engineering',
    'PRC Board Exam - Real Estate Brokerage',
    # Civil service
    'Civil Service Eligibility - Professional',
    'Civil Service Eligibility - Sub-Professional',
    'Civil Service Eligibility - Career Service',
    # Cloud / IT
    'AWS Certified Cloud Practitioner', 'AWS Certified Solutions Architect',
    'AWS Certified Developer', 'AWS Certified SysOps Administrator',
    'Microsoft Certified: Azure Fundamentals',
    'Microsoft Certified: Azure Administrator',
    'Microsoft Certified: Azure Developer',
    'Microsoft Certified: Power BI Data Analyst',
    'Google IT Support Certificate', 'Google Data Analytics Certificate',
    'Google UX Design Certificate', 'Google Project Management Certificate',
    'Google Cloud Associate Cloud Engineer',
    'Cisco CCNA', 'Cisco CCNP', 'CompTIA A+', 'CompTIA Network+',
    'CompTIA Security+', 'Oracle Java Certification',
    'Oracle Database Administrator',
    'Certified Kubernetes Administrator', 'Docker Certified Associate',
    # Project management / process
    'PMP (Project Management Professional)',
    'Certified Scrum Master', 'PRINCE2', 'Lean Six Sigma Yellow Belt',
    'Lean Six Sigma Green Belt', 'Lean Six Sigma Black Belt',
    'ITIL Foundation',
    # Safety / first aid / health
    'First Aid and Basic Life Support', 'Basic Life Support (BLS)',
    'Advanced Cardiac Life Support (ACLS)',
    'BOSH Training Certificate', 'COSH Training Certificate',
    'Occupational Health and Safety', 'Food Safety Certificate',
    'HACCP Certification', 'Fire Safety Officer',
    'Red Cross First Aid', 'Red Cross CPR',
    # Driving / vehicles
    'LTO Non-Professional Driver\'s License',
    'LTO Professional Driver\'s License',
    'Forklift Operator Certificate', 'OFW Seafarer Documentation',
    # Other
    'Real Estate Salesperson Accreditation',
    'Insurance Commission License',
]


STATIC_INSTITUTIONS = [
    # Iloilo City universities and colleges
    'University of the Philippines Visayas',
    'West Visayas State University',
    'Central Philippine University',
    'University of San Agustin',
    'University of Iloilo - PHINMA',
    'Iloilo Doctors\' College',
    'John B. Lacson Foundation Maritime University',
    'St. Paul University Iloilo',
    'St. Therese-MTC Colleges',
    'Iloilo Science and Technology University',
    'University of the East - Iloilo',
    'Western Institute of Technology',
    'Colegio de las Hijas de Jesús',
    'Hua Siong College of Iloilo',
    'Northern Iloilo Polytechnic State College',
    'University of Antique',
    'Ateneo de Iloilo - Sta. Maria Catholic School',
    'Assumption Iloilo',
    'STI College Iloilo',
    'AMA Computer College - Iloilo',
    'ABE International Business College - Iloilo',
    'Riverside College',
    'Western Visayas College of Science and Technology',
    # Iloilo City high schools
    'Iloilo National High School',
    'Iloilo City National High School',
    'La Paz National High School',
    'Jaro National High School',
    'Mandurriao National High School',
    'Lanit National High School',
    'Pedro Zarraga Memorial National High School',
    'Iloilo Central Commercial High School (ICCHS)',
    'St. Joseph\'s Regional Seminary',
    # Province-wide / common reference
    'Iloilo State College of Fisheries',
    'Capiz State University',
    'Aklan State University',
    'University of San Carlos',
    'Silliman University',
    'De La Salle University',
    'Ateneo de Manila University',
    'University of the Philippines Diliman',
    'University of Santo Tomas',
    'Polytechnic University of the Philippines',
    'Mapúa University',
    'Far Eastern University',
    'Adamson University',
    # TESDA training centers
    'TESDA Iloilo Provincial Training Center',
    'TESDA Regional Training Center - Region VI',
]

STATIC_COMPANIES = [
    # Government / public sector (Iloilo / Region VI)
    'Iloilo City Government', 'Iloilo Provincial Government',
    'PESO Iloilo City', 'Department of Trade and Industry - Region VI',
    'Department of Education - Iloilo', 'Department of Health - Region VI',
    'Department of Social Welfare and Development - Region VI',
    'Department of Science and Technology - Region VI',
    'Department of Public Works and Highways - Region VI',
    'Department of Labor and Employment - Region VI',
    'Bureau of Internal Revenue - Iloilo',
    'Social Security System (SSS)', 'GSIS',
    'Philippine Statistics Authority',
    # Hospitals (Iloilo)
    'Western Visayas Medical Center', 'Iloilo Mission Hospital',
    'St. Paul\'s Hospital Iloilo', 'The Medical City Iloilo',
    'Iloilo Doctors\' Hospital', 'Western Visayas Sanitarium',
    'Qualimed Hospital - Iloilo',
    # Banks (with Iloilo branches)
    'BDO Unibank', 'BPI', 'Metrobank', 'Land Bank of the Philippines',
    'Development Bank of the Philippines', 'PNB', 'UnionBank',
    'Security Bank', 'China Bank', 'EastWest Bank', 'RCBC',
    'Iloilo Economy Bank', 'Sterling Bank of Asia',
    # Retail / malls
    'SM City Iloilo', 'SM Supermalls', 'Robinsons Place Iloilo',
    'Robinsons Land Corporation', 'Festive Walk Mall', 'Atria Park District',
    'Gaisano Capital Iloilo', 'Puregold Iloilo', 'Mercury Drug',
    'Watsons', '7-Eleven', 'Ministop',
    # BPO / shared services in Iloilo
    'Teleperformance', 'Concentrix', 'Reed Elsevier (RELX)',
    'Transcom', 'Ubiquity Global Services', 'Telus International',
    'Sykes Asia', 'TaskUs', 'SPI Global', 'Iqor', 'IBM',
    # Telco
    'PLDT', 'Globe Telecom', 'Smart Communications', 'DITO Telecommunity',
    'Converge ICT Solutions',
    # Utilities
    'MORE Power (Iloilo)', 'Panay Electric Company',
    'Iloilo Bulk Water Supply', 'Metro Iloilo Water District',
    # Maritime / transport
    '2GO Travel', 'Cokaliong Shipping Lines', 'Montenegro Shipping Lines',
    'Cebu Pacific', 'Philippine Airlines', 'AirAsia Philippines',
    'Iloilo International Airport',
    # Conglomerates / large employers
    'Megaworld Corporation', 'Ayala Land', 'Ayala Corporation',
    'San Miguel Corporation', 'Aboitiz Equity Ventures', 'JG Summit Holdings',
    'GT Capital Holdings', 'Universal Robina Corporation',
    'Jollibee Foods Corporation', 'McDonald\'s Philippines',
    'Max\'s Restaurant', 'Mang Inasal',
    'Globe Business', 'Coca-Cola Beverages Philippines',
    'Pepsi-Cola Products Philippines',
    # Education employers
    'Central Philippine University', 'University of San Agustin',
    'West Visayas State University',
    'Department of Education',
]


def _autocomplete_response(query, db_values, static_values, cache_key):
    """Shared autocomplete logic: merge DB + static vocab, then smart-rank."""
    if not query:
        return JsonResponse([], safe=False)
    from apps.jobseekers.nlp_service import smart_rank
    candidates = list(dict.fromkeys(list(db_values) + list(static_values)))
    suggestions = smart_rank(query, candidates, limit=10, cache_key=cache_key)
    return JsonResponse(suggestions, safe=False)


def autocomplete_skills(request):
    query = request.GET.get('q', '').strip()
    from apps.jobseekers.models import Skill as JobseekerSkill
    db_skills = JobseekerSkill.objects.values_list('name', flat=True).distinct()
    return _autocomplete_response(query, db_skills, STATIC_SKILLS, cache_key='skills')


def autocomplete_positions(request):
    query = request.GET.get('q', '').strip()
    db_positions = JobPosting.objects.filter(status='open').values_list(
        'title', flat=True).distinct()
    return _autocomplete_response(query, db_positions, STATIC_POSITIONS, cache_key='positions')


def autocomplete_degrees(request):
    query = request.GET.get('q', '').strip()
    # Degrees: static only (canonical PH degree list is comprehensive)
    return _autocomplete_response(query, [], STATIC_DEGREES, cache_key='degrees')


def autocomplete_certifications(request):
    query = request.GET.get('q', '').strip()
    from apps.jobseekers.models import Certification as JobseekerCert
    db_certs = JobseekerCert.objects.values_list('name', flat=True).distinct()
    return _autocomplete_response(query, db_certs, STATIC_CERTS, cache_key='certs')


def autocomplete_institutions(request):
    query = request.GET.get('q', '').strip()
    from apps.jobseekers.models import Education
    db_institutions = (
        Education.objects.exclude(institution='')
        .values_list('institution', flat=True).distinct()
    )
    return _autocomplete_response(query, db_institutions, STATIC_INSTITUTIONS, cache_key='institutions')


def autocomplete_companies(request):
    query = request.GET.get('q', '').strip()
    from apps.jobseekers.models import WorkExperience
    from apps.employers.models import Company
    db_companies = list(
        WorkExperience.objects.exclude(company='')
        .values_list('company', flat=True).distinct()
    )
    db_companies += list(Company.objects.values_list('name', flat=True).distinct())
    return _autocomplete_response(query, db_companies, STATIC_COMPANIES, cache_key='companies')