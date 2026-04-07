from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.jobs.models import JobPosting
from apps.jobseekers.models import (
    JobseekerProfile, Education, Skill,
    Certification, WorkExperience, Sector
)
from datetime import datetime



@login_required
def dashboard(request):
    if not request.user.is_jobseeker:
        return redirect('/employers/dashboard/')

    try:
        profile = request.user.jobseeker_profile
    except JobseekerProfile.DoesNotExist:
        return redirect('/register/info/')

    from apps.matching.engine import get_ranked_jobs
    from apps.jobs.models import JobPosting

    education = Education.objects.filter(profile=profile)
    skills = Skill.objects.filter(profile=profile)
    certifications = Certification.objects.filter(profile=profile)
    recent_jobs = JobPosting.objects.filter(status='open').order_by('-created_at')[:5]

    # Get ranked jobs for this jobseeker
    if profile.profile_complete:
        ranked_jobs = get_ranked_jobs(profile)[:5]
    else:
        ranked_jobs = []

    return render(request, 'jobseekers/dashboard.html', {
        'profile': profile,
        'education': education,
        'skills': skills,
        'certifications': certifications,
        'recent_jobs': recent_jobs,
        'ranked_jobs': ranked_jobs,
        'unread_notifications': False,
        'unread_messages': False,
    })


@login_required
def resume(request):
    if not request.user.is_jobseeker:
        return redirect('/employers/dashboard/')

    try:
        profile = request.user.jobseeker_profile
    except JobseekerProfile.DoesNotExist:
        return redirect('/register/info/')

    if request.method == 'POST':
        # Update profile fields
        profile.job_search_query = request.POST.get('job_search_query', '')
        profile.house_unit = request.POST.get('house_unit', '')
        profile.street_barangay = request.POST.get('street_barangay', '')
        province_code = request.POST.get('province', '')
        city_code = request.POST.get('city_municipality', '')
        profile.province = 'Iloilo'
        profile.province_code = '063000000'
        profile.city_code = city_code

        from apps.core.models import CityMunicipality, Barangay
        try:
            profile.city_municipality = CityMunicipality.objects.get(code=city_code).name
        except CityMunicipality.DoesNotExist:
            profile.city_municipality = ''
        barangay_code = request.POST.get('barangay', '')
        profile.barangay_code = barangay_code
        from apps.core.models import Province, CityMunicipality, Barangay
        try:
            profile.barangay = Barangay.objects.get(code=barangay_code).name
        except Barangay.DoesNotExist:
            profile.barangay = ''

        # Save human-readable names
        from apps.core.models import Province, CityMunicipality, Barangay
        try:
            profile.province = Province.objects.get(code=province_code).name
        except Province.DoesNotExist:
            profile.province = ''
        try:
            profile.city_municipality = CityMunicipality.objects.get(code=city_code).name
        except CityMunicipality.DoesNotExist:
            profile.city_municipality = ''
            
        profile.phone = request.POST.get('phone', '')
        profile.contact_email = request.POST.get('contact_email', '')
        profile.save()

        # Education
        Education.objects.filter(profile=profile).delete()
        levels = request.POST.getlist('edu_level')
        courses = request.POST.getlist('edu_course')
        starts = request.POST.getlist('edu_start')
        ends = request.POST.getlist('edu_end')
        is_currents = request.POST.getlist('edu_is_current')
        for i, level in enumerate(levels):
            if not level:
                continue
            Education.objects.create(
                profile=profile,
                level=level,
                course_degree=courses[i] if i < len(courses) else '',
                year_started=starts[i] if i < len(starts) and starts[i] else None,
                year_ended=ends[i] if i < len(ends) and ends[i] else None,
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

        # Work Experience
        WorkExperience.objects.filter(profile=profile).delete()
        positions = request.POST.getlist('exp_position')
        descriptions = request.POST.getlist('exp_description')
        start_months = request.POST.getlist('exp_start_month')
        start_years = request.POST.getlist('exp_start_year')
        end_months = request.POST.getlist('exp_end_month')
        end_years = request.POST.getlist('exp_end_year')
        companies = request.POST.getlist('exp_company')
        exp_is_currents = request.POST.getlist('exp_is_current')
        for i, position in enumerate(positions):
            if not position:
                continue
            WorkExperience.objects.create(
                profile=profile,
                position=position,
                company=companies[i] if i < len(companies) else '',
                description=descriptions[i] if i < len(descriptions) else '',
                month_started=start_months[i] if i < len(start_months) else '',
                year_started=start_years[i] if i < len(start_years) and start_years[i] else None,
                month_ended=end_months[i] if i < len(end_months) else '',
                year_ended=end_years[i] if i < len(end_years) and end_years[i] else None,
                is_current=str(i) in exp_is_currents,
            )

        # Sectors
        profile.sectors.clear()
        profile.sectors.set(request.POST.getlist('sectors'))
        profile.profile_complete = True
        profile.save()

        return redirect('/dashboard/')

    education = Education.objects.filter(profile=profile)
    skills = Skill.objects.filter(profile=profile)
    certifications = Certification.objects.filter(profile=profile)
    experiences = WorkExperience.objects.filter(profile=profile)
    sectors = Sector.objects.all()

    return render(request, 'jobseekers/resume.html', {
        'profile': profile,
        'education': education,
        'skills': skills,
        'certifications': certifications,
        'experiences': experiences,
        'sectors': sectors,
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
    except:
        return redirect('/register/info/')

    from apps.matching.engine import get_ranked_jobs

    if profile.profile_complete:
        ranked_jobs = get_ranked_jobs(profile)
    else:
        ranked_jobs = []

    return render(request, 'jobseekers/recommended_jobs.html', {
        'profile': profile,
        'ranked_jobs': ranked_jobs,
        'unread_notifications': False,
        'unread_messages': False,
    })

@login_required
def job_save(request, job_id):
    if request.method != 'POST':
        return redirect('/jobs/for-you/')
    from apps.jobseekers.models import JobInteraction
    from apps.jobs.models import JobPosting
    profile = request.user.jobseeker_profile
    job = get_object_or_404(JobPosting, id=job_id)

    existing = JobInteraction.objects.filter(jobseeker=profile, job=job).first()
    if existing:
        if existing.interaction_type == JobInteraction.LIKED:
            existing.delete()  # toggle off
        else:
            existing.interaction_type = JobInteraction.LIKED
            existing.save()  # switch from hidden to liked
    else:
        JobInteraction.objects.create(
            jobseeker=profile,
            job=job,
            interaction_type=JobInteraction.LIKED
        )

    return redirect(request.POST.get('next', '/jobs/for-you/'))


@login_required
def job_hide(request, job_id):
    if request.method != 'POST':
        return redirect('/jobs/for-you/')
    from apps.jobseekers.models import JobInteraction
    from apps.jobs.models import JobPosting
    profile = request.user.jobseeker_profile
    job = get_object_or_404(JobPosting, id=job_id)

    existing = JobInteraction.objects.filter(jobseeker=profile, job=job).first()
    if existing:
        if existing.interaction_type == JobInteraction.HIDDEN:
            existing.delete()  # toggle off
        else:
            existing.interaction_type = JobInteraction.HIDDEN
            existing.save()  # switch from liked to hidden
    else:
        JobInteraction.objects.create(
            jobseeker=profile,
            job=job,
            interaction_type=JobInteraction.HIDDEN
        )

    return redirect(request.POST.get('next', '/jobs/for-you/'))