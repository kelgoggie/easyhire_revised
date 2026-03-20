"""
EasyHire Matching Engine
========================
Computes a 0–100 compatibility score between a JobseekerProfile and a JobPosting.

Scoring formula (weighted sum):
  score = (w_skill  * skill_score)
        + (w_edu    * edu_score)
        + (w_exp    * exp_score)
        + (w_cert   * cert_score)
        + (w_sector * sector_score)

Weights sum to 1.0 and can be tuned in SCORE_WEIGHTS below.
"""

from rapidfuzz import fuzz, process

# --- Configurable weights ---
SCORE_WEIGHTS = {
    "skills":         0.35,
    "education":      0.25,
    "experience":     0.20,
    "certifications": 0.10,
    "sector":         0.10,
}

# Education level ordering (higher index = higher level)
EDUCATION_LEVELS = [
    "elementary",
    "high_school",
    "senior_high",
    "vocational",
    "associate",
    "bachelor",
    "master",
    "doctorate",
]

FUZZY_THRESHOLD = 75  # minimum rapidfuzz score (0–100) to count as a match


def compute_score(jobseeker, job) -> dict:
    """
    Main entry point. Returns a dict:
    {
      'score': float (0–100),
      'breakdown': { category: { 'score': float, ... } }
    }
    """
    requirements = list(job.requirements.all())

    skill_score  = _score_skills(jobseeker, requirements)
    edu_score    = _score_education(jobseeker, requirements)
    exp_score    = _score_experience(jobseeker, requirements)
    cert_score   = _score_certifications(jobseeker, requirements)
    sector_score = _score_sector(jobseeker, job)

    scores = {
        "skills":         skill_score,
        "education":      edu_score,
        "experience":     exp_score,
        "certifications": cert_score,
        "sector":         sector_score,
    }

    final = sum(SCORE_WEIGHTS[k] * v["score"] for k, v in scores.items())

    return {
        "score":     round(final, 2),
        "breakdown": scores,
    }


def _score_skills(jobseeker, requirements) -> dict:
    required = [r.value for r in requirements if r.req_type == "skill" and r.is_required]
    preferred = [r.value for r in requirements if r.req_type == "skill" and not r.is_required]

    if not required and not preferred:
        return {"score": 100.0, "matched": [], "missing": []}

    jobseeker_skills = [s.name for s in jobseeker.skills.all()]
    matched, missing = [], []

    for req_skill in required:
        best_match = process.extractOne(req_skill, jobseeker_skills, scorer=fuzz.token_sort_ratio)
        if best_match and best_match[1] >= FUZZY_THRESHOLD:
            matched.append(req_skill)
        else:
            missing.append(req_skill)

    # Required skills: full weight. Preferred skills add bonus up to the preferred bucket.
    required_score  = (len(matched) / len(required) * 100) if required else 100.0
    preferred_bonus = 0.0
    if preferred:
        pref_matched = sum(
            1 for s in preferred
            if process.extractOne(s, jobseeker_skills, scorer=fuzz.token_sort_ratio)
            and process.extractOne(s, jobseeker_skills, scorer=fuzz.token_sort_ratio)[1] >= FUZZY_THRESHOLD
        )
        preferred_bonus = (pref_matched / len(preferred)) * 20  # up to +20 pts

    score = min(100.0, required_score + preferred_bonus)
    return {"score": round(score, 2), "matched": matched, "missing": missing}


def _score_education(jobseeker, requirements) -> dict:
    edu_reqs = [r for r in requirements if r.req_type == "education"]
    if not edu_reqs:
        return {"score": 100.0}

    required_level = edu_reqs[0].value.lower().replace("'s degree", "").replace(" degree", "").strip()
    required_idx   = next((i for i, lvl in enumerate(EDUCATION_LEVELS) if required_level in lvl), 0)

    # Get the jobseeker's highest education level
    best_edu = max(
        (e for e in jobseeker.educations.all()),
        key=lambda e: EDUCATION_LEVELS.index(e.level) if e.level in EDUCATION_LEVELS else -1,
        default=None
    )
    if best_edu is None:
        return {"score": 0.0}

    jobseeker_idx = EDUCATION_LEVELS.index(best_edu.level) if best_edu.level in EDUCATION_LEVELS else 0

    if jobseeker_idx >= required_idx:
        return {"score": 100.0}
    # Partial credit: one level below = 60%, two below = 30%, more = 0
    diff = required_idx - jobseeker_idx
    score = max(0.0, 100.0 - (diff * 40))
    return {"score": round(score, 2)}


def _score_experience(jobseeker, requirements) -> dict:
    exp_reqs = [r for r in requirements if r.req_type == "experience"]
    if not exp_reqs:
        return {"score": 100.0}

    # Parse required years (e.g. "2 years" → 2)
    try:
        required_years = float(exp_reqs[0].value.split()[0])
    except (ValueError, IndexError):
        return {"score": 100.0}

    # Calculate total years of work experience
    total_months = 0
    for exp in jobseeker.experiences.all():
        start = (exp.year_started or 0) * 12
        if exp.is_current:
            from django.utils import timezone
            end = timezone.now().year * 12 + timezone.now().month
        else:
            end = (exp.year_ended or exp.year_started or 0) * 12
        total_months += max(0, end - start)

    jobseeker_years = total_months / 12
    if jobseeker_years >= required_years:
        return {"score": 100.0}

    score = (jobseeker_years / required_years) * 100 if required_years > 0 else 100.0
    return {"score": round(score, 2), "years_have": round(jobseeker_years, 1), "years_need": required_years}


def _score_certifications(jobseeker, requirements) -> dict:
    cert_reqs = [r for r in requirements if r.req_type == "certification"]
    if not cert_reqs:
        return {"score": 100.0, "matched": [], "missing": []}

    jobseeker_certs = [c.name for c in jobseeker.certifications.all()]
    matched, missing = [], []

    for req_cert in cert_reqs:
        best = process.extractOne(req_cert.value, jobseeker_certs, scorer=fuzz.token_sort_ratio)
        if best and best[1] >= FUZZY_THRESHOLD:
            matched.append(req_cert.value)
        else:
            missing.append(req_cert.value)

    score = (len(matched) / len(cert_reqs) * 100) if cert_reqs else 100.0
    return {"score": round(score, 2), "matched": matched, "missing": missing}


def _score_sector(jobseeker, job) -> dict:
    """
    Full score if the company's sector badges overlap with the jobseeker's sectors.
    If neither has sector data, neutral (100). If company has badges but jobseeker
    has no sectors, still neutral (we don't penalize — sector is inclusive, not exclusive).
    """
    company_badges  = set(job.company.sector_badges or [])
    jobseeker_sectors = set(jobseeker.sectors or [])

    if not company_badges or not jobseeker_sectors:
        return {"score": 100.0}

    overlap = company_badges & jobseeker_sectors
    score = (len(overlap) / len(jobseeker_sectors)) * 100 if jobseeker_sectors else 100.0
    return {"score": round(min(score, 100.0), 2), "matched_sectors": list(overlap)}
