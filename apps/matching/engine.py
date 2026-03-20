from rapidfuzz import fuzz
from apps.jobseekers.models import Education, Skill, Certification, WorkExperience


# ── Weight constants ───────────────────────────────────────────────────────────
WEIGHT_SKILLS = 0.35
WEIGHT_EDUCATION = 0.25
WEIGHT_EXPERIENCE = 0.20
WEIGHT_CERTIFICATIONS = 0.10
WEIGHT_SECTOR = 0.10

FUZZY_THRESHOLD = 75


def fuzzy_match(a, b):
    return fuzz.token_set_ratio(a.lower(), b.lower()) >= FUZZY_THRESHOLD


def score_education(job, profile):
    try:
        req = job.education_requirement
    except Exception:
        return 1.0

    LEVEL_ORDER = [
        "elementary", "junior_high", "senior_high", "vocational",
        "associate", "bachelor", "master", "doctorate",
    ]

    req_index = LEVEL_ORDER.index(req.level) if req.level in LEVEL_ORDER else 0
    educations = Education.objects.filter(profile=profile)

    if not educations.exists():
        return 0.0

    jobseeker_indices = [
        LEVEL_ORDER.index(edu.level)
        for edu in educations
        if edu.level in LEVEL_ORDER
    ]

    if not jobseeker_indices:
        return 0.0

    highest = max(jobseeker_indices)

    if highest >= req_index:
        return 1.0
    elif highest == req_index - 1:
        return 0.5
    else:
        return 0.0


def score_experience(job, profile):
    try:
        req = job.experience_requirement
    except Exception:
        return 1.0

    required_years = req.years_required
    if required_years == 0:
        return 1.0

    experiences = WorkExperience.objects.filter(profile=profile)
    if not experiences.exists():
        return 0.0

    total_years = 0
    for exp in experiences:
        start = exp.year_started
        end = exp.year_ended
        if start:
            try:
                start_y = int(start)
                if exp.is_current:
                    from datetime import date
                    end_y = date.today().year
                elif end:
                    end_y = int(end)
                else:
                    end_y = start_y
                total_years += max(0, end_y - start_y)
            except (ValueError, TypeError):
                pass

    if total_years >= required_years:
        return 1.0
    else:
        return round(total_years / required_years, 2)


def score_skills(job, profile):
    required_skills = job.skill_requirements.filter(is_required=True)
    if not required_skills.exists():
        return 1.0

    jobseeker_skills = [s.name for s in Skill.objects.filter(profile=profile)]
    if not jobseeker_skills:
        return 0.0

    matched = 0
    for req_skill in required_skills:
        for js_skill in jobseeker_skills:
            if fuzzy_match(req_skill.name, js_skill):
                matched += 1
                break

    return round(matched / required_skills.count(), 2)


def score_certifications(job, profile):
    required_certs = job.certification_requirements.filter(is_required=True)
    if not required_certs.exists():
        return 1.0

    jobseeker_certs = [c.name for c in Certification.objects.filter(profile=profile)]
    if not jobseeker_certs:
        return 0.0

    matched = 0
    for req_cert in required_certs:
        for js_cert in jobseeker_certs:
            if fuzzy_match(req_cert.name, js_cert):
                matched += 1
                break

    return round(matched / required_certs.count(), 2)


def score_sector(job, profile):
    company_sectors = set(job.company.sector_badges.values_list('id', flat=True))
    if not company_sectors:
        return 1.0

    jobseeker_sectors = set(profile.sectors.values_list('id', flat=True))
    if not jobseeker_sectors:
        return 0.0

    return 1.0 if company_sectors & jobseeker_sectors else 0.0


def compute_match_score(job, profile):
    edu = score_education(job, profile)
    exp = score_experience(job, profile)
    skills = score_skills(job, profile)
    certs = score_certifications(job, profile)
    sector = score_sector(job, profile)

    total = (
        skills * WEIGHT_SKILLS +
        edu * WEIGHT_EDUCATION +
        exp * WEIGHT_EXPERIENCE +
        certs * WEIGHT_CERTIFICATIONS +
        sector * WEIGHT_SECTOR
    )

    return {
        'total': round(total * 100),
        'breakdown': {
            'skills': round(skills * 100),
            'education': round(edu * 100),
            'experience': round(exp * 100),
            'certifications': round(certs * 100),
            'sector': round(sector * 100),
        }
    }


def get_ranked_jobseekers(job):
    from apps.jobseekers.models import JobseekerProfile
    jobseekers = JobseekerProfile.objects.filter(profile_complete=True)
    results = []
    for profile in jobseekers:
        score = compute_match_score(job, profile)
        results.append({
            'profile': profile,
            'score': score['total'],
            'breakdown': score['breakdown'],
        })
    results.sort(key=lambda x: x['score'], reverse=True)
    return results


def get_ranked_jobs(profile):
    from apps.jobs.models import JobPosting
    jobs = JobPosting.objects.filter(status='open')
    results = []
    for job in jobs:
        score = compute_match_score(job, profile)
        results.append({
            'job': job,
            'score': score['total'],
            'breakdown': score['breakdown'],
        })
    results.sort(key=lambda x: x['score'], reverse=True)
    return results