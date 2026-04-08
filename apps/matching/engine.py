from rapidfuzz import fuzz
from apps.jobseekers.models import Education, Skill, Certification, WorkExperience


# ── Weights (sector removed, redistributed to skills + education) ──
WEIGHT_SKILLS = 0.40        # +5% from sector removal
WEIGHT_EDUCATION = 0.30     # +5% from sector removal
WEIGHT_EXPERIENCE = 0.20
WEIGHT_CERTIFICATIONS = 0.10

# ── Preferred skills bonus (applied on top of required skills score) ──
PREFERRED_SKILLS_BONUS = 0.15   # up to 15% of the skills score

# ── Fuzzy matching threshold ──
FUZZY_THRESHOLD = 75

# ── Query boost (multiplier on total score when job_search_query is set) ──
QUERY_BOOST_MAX = 0.10  # up to 10% boost on top of total score


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

    if highest < req_index - 1:
        return 0.0

    if highest == req_index - 1:
        return 0.5

    # ── Level is met (highest >= req_index) ──
    # If job specifies no particular course, level alone is sufficient
    if not req.course_degree:
        return 1.0

    # Check if any of the jobseeker's qualifying education entries
    # (at or above required level) match the required course
    qualifying_educations = [
        edu for edu in educations
        if edu.level in LEVEL_ORDER and LEVEL_ORDER.index(edu.level) >= req_index
    ]

    for edu in qualifying_educations:
        if edu.course_degree and fuzzy_match(req.course_degree, edu.course_degree):
            return 1.0

    # Level met but course doesn't match
    return 0.6


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
    preferred_skills = job.skill_requirements.filter(is_required=False)
    jobseeker_skills = [s.name for s in Skill.objects.filter(profile=profile)]

    if not jobseeker_skills:
        return 0.0

    # ── Required skills score ──
    if required_skills.exists():
        matched_required = 0
        for req_skill in required_skills:
            for js_skill in jobseeker_skills:
                if fuzzy_match(req_skill.name, js_skill):
                    matched_required += 1
                    break
        required_score = matched_required / required_skills.count()
    else:
        required_score = 1.0

    # ── Preferred skills bonus ──
    # Only applied if there are preferred skills and jobseeker matches some
    preferred_bonus = 0.0
    if preferred_skills.exists():
        matched_preferred = 0
        for pref_skill in preferred_skills:
            for js_skill in jobseeker_skills:
                if fuzzy_match(pref_skill.name, js_skill):
                    matched_preferred += 1
                    break
        # Bonus scales up to PREFERRED_SKILLS_BONUS based on proportion matched
        preferred_ratio = matched_preferred / preferred_skills.count()
        preferred_bonus = preferred_ratio * PREFERRED_SKILLS_BONUS

    # Cap total at 1.0
    total = min(1.0, required_score + (required_score * preferred_bonus))
    return round(total, 2)


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


def score_query_boost(job, profile):
    """
    Boosts score when the jobseeker's job_search_query matches the job.
    Returns a boost value between 0.0 and QUERY_BOOST_MAX.
    If no query is set, returns 0.0 (neutral — no effect on score).
    """
    query = getattr(profile, 'job_search_query', '').strip()
    if not query:
        return 0.0

    targets = [
        job.title,
        job.description,
    ] + [s.name for s in job.skill_requirements.all()]

    best_ratio = max(
        fuzz.token_set_ratio(query.lower(), t.lower())
        for t in targets
        if t
    )

    # Scale: 75+ threshold → linear scale to QUERY_BOOST_MAX
    if best_ratio < FUZZY_THRESHOLD:
        return 0.0

    boost = ((best_ratio - FUZZY_THRESHOLD) / (100 - FUZZY_THRESHOLD)) * QUERY_BOOST_MAX
    return round(boost, 3)


def score_sector_match(job, profile):
    """
    Post-scoring sector filter.
    Returns True if the jobseeker shares at least one sector with the company,
    or if either side has no sectors defined.
    """
    company_sectors = set(job.company.sector_badges.values_list('id', flat=True))
    if not company_sectors:
        return True

    jobseeker_sectors = set(profile.sectors.values_list('id', flat=True))
    if not jobseeker_sectors:
        return True

    return bool(company_sectors & jobseeker_sectors)


def compute_match_score(job, profile):
    edu = score_education(job, profile)
    exp = score_experience(job, profile)
    skills = score_skills(job, profile)
    certs = score_certifications(job, profile)

    base_score = (
        skills * WEIGHT_SKILLS +
        edu * WEIGHT_EDUCATION +
        exp * WEIGHT_EXPERIENCE +
        certs * WEIGHT_CERTIFICATIONS
    )

    # Apply query boost on top of base score
    query_boost = score_query_boost(job, profile)
    total = min(1.0, base_score + query_boost)

    return {
        'total': round(total * 100),
        'breakdown': {
            'skills': round(skills * 100),
            'education': round(edu * 100),
            'experience': round(exp * 100),
            'certifications': round(certs * 100),
            'query_boost': round(query_boost * 100),
        },
        'sector_match': score_sector_match(job, profile),
    }


def get_ranked_jobseekers(job, sector_filter=False):
    """
    Returns jobseekers ranked by match score for a given job.
    If sector_filter=True, only returns jobseekers with a sector match.
    """
    from apps.jobseekers.models import JobseekerProfile
    jobseekers = JobseekerProfile.objects.filter(profile_complete=True)
    results = []
    for profile in jobseekers:
        score = compute_match_score(job, profile)
        if sector_filter and not score['sector_match']:
            continue
        results.append({
            'profile': profile,
            'score': score['total'],
            'breakdown': score['breakdown'],
            'sector_match': score['sector_match'],
        })
    results.sort(key=lambda x: x['score'], reverse=True)
    return results


def get_ranked_jobs(profile, sector_filter=False):
    from apps.jobs.models import JobPosting
    jobs = JobPosting.objects.filter(status='open').select_related(
        'company', 'education_requirement', 'experience_requirement'
    ).prefetch_related('skill_requirements', 'certification_requirements')

    results = []
    for job in jobs:
        score = compute_match_score(job, profile)
        if sector_filter and not score['sector_match']:
            continue
        results.append({
            'job': job,
            'score': score['total'],
            'breakdown': score['breakdown'],
            'sector_match': score['sector_match'],
        })

    # ── Query-based tiering ────────────────────────────────────────
    query = getattr(profile, 'job_search_query', '').strip()
    if query:
        from rapidfuzz import fuzz
        def matches_query(item):
            targets = [
                item['job'].title,
                item['job'].description,
            ] + [s.name for s in item['job'].skill_requirements.all()]
            best = max(
                fuzz.token_set_ratio(query.lower(), t.lower())
                for t in targets if t
            )
            return best >= FUZZY_THRESHOLD

        preferred = [r for r in results if matches_query(r)]
        others = [r for r in results if not matches_query(r)]

        # Sort each tier by score descending
        preferred.sort(key=lambda x: x['score'], reverse=True)
        others.sort(key=lambda x: x['score'], reverse=True)

        results = preferred + others
    else:
        results.sort(key=lambda x: x['score'], reverse=True)

    return results