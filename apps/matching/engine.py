from rapidfuzz import fuzz
from apps.jobseekers.models import Education, Skill, Certification, WorkExperience


# ── Weights (core 4 add up to 1.0) ────────────────────────────────
WEIGHT_SKILLS = 0.40
WEIGHT_EDUCATION = 0.25
WEIGHT_EXPERIENCE = 0.25
WEIGHT_CERTIFICATIONS = 0.10

# ── Post-score boosters ────────────────────────────────────────────
QUERY_BOOST_MAX = 0.10   # up to 10% boost
LOCATION_BOOST_MAX = 0.10  # up to 10% boost

# ── Fuzzy matching threshold ───────────────────────────────────────
FUZZY_THRESHOLD = 75


# ── Iloilo City District Map ───────────────────────────────────────
# Official PSGC-based district groupings for Iloilo City
# Each barangay name is stored as it appears in the PSGC database

ILOILO_DISTRICTS = {
    'city_proper': [
        'Agasan', 'Assumption', 'Bonifacio (Asluman)', 'Buhang', 'Buhang Taft North',
        'Buntatala', 'Camalig', 'Cochero', 'Compania', 'Concepcion-Montes',
        'Danao', 'Delgado-Jalandoni-Bagumbayan', 'Demo', 'Desamparados',
        'Dungon A', 'Dungon B', 'Dungon C', 'East Baluarte', 'East Timawa',
        'Edganzon', 'El 98 Speedway (Rizal Paraje)', 'Fajardo', 'Flores',
        'General Hughes-Montes', 'Gloria', 'Gustilo', 'Hibao-an Norte',
        'Hibao-an Sur', 'Hinactaanan', 'Infante', 'Ingore', 'Jalandoni Estate-Pilane',
        'Kahirup', "La Paz", 'Laguda', 'Lanit', 'Lapuz Norte', 'Lapuz Sur',
        'Libertad', 'Linog', 'Lopez Jaena Norte', 'Lopez Jaena Sur',
        'Luna (Magsaysay)', 'M. V. Hechanova', 'Mabolo-Delgado', 'Macatol',
        'Magdalo', 'Magsaysay Village', 'Mansaya-Lapuz', 'Marcelo H. del Pilar',
        'Maria Clara', 'Molo Boulevard', 'Montinola', 'Motorpool',
        'Naga-Ilaya (La Paz)', 'Nabitasan', 'Navais', 'Nonoy',
        'North Baluarte', 'North Fundidor', 'North San Jose',
        'Obrero-Lapuz', 'Oñate de Leon', 'Ortiz',
        'Osmeña', 'Our Lady of Fatima', 'Our Lady of Lourdes',
        'Pablo Lavezares', 'Pale Benedicto Rizal (Mandurriao)', 'Pena-Gomburza',
        'People\'s Park', 'Progreso-Lapuz', 'Punong-Lapuz',
        'Quezon', 'Quintin Salas', 'Railway (Iloilo City Proper)',
        'Remu-Lapuz', 'Rizal', 'Rizal Estanzuela', 'Rizal Ibabao',
        'Rizal Palapala I', 'Rizal Palapala II',
        'Rojas', 'San Agustin', 'San Felix', 'San Isidro (Jaro)',
        'San Jose', 'San Pedro', 'Santa Cruz', 'Santa Filomena',
        'Santa Isabel', 'Santa Remedios', 'Santa Rosa',
        'Santo Domingo', 'Santo Niño Norte', 'Santo Niño Sur',
        'Santos Escario', 'Seminario (Burgos-Mabini)', 'Simon Ledesma',
        'Sinikway (Bangkerohan Lapuz)', 'South Baluarte', 'South Fundidor',
        'South San Jose', 'Taal', 'Tabuc Suba (Jaro)', 'Taytay Zone II',
        'Taytay Zone III', 'Taytay Zone IV', 'Ticud (La Paz)',
        'Timawa Tanza I', 'Timawa Tanza II',
        'Veterans Village', 'Villa Anita', 'West Habog-Habog',
        'West Timawa', 'Yulo Drive', 'Zamora-Melliza',
    ],
    'jaro': [
        'Aguinaldo', 'Alimodian (Calahunan)', 'Asam', 'Balabago',
        'Balantang', 'Baldoza', 'Bantud', 'Bantud Fabrica Road',
        'Barangay I Pob. (Jaro)', 'Barangay II Pob. (Jaro)',
        'Barangay III Pob. (Jaro)', 'Barangay IV Pob. (Jaro)',
        'Barangay V Pob. (Jaro)', 'Bitoon', 'Bito-on',
        'Bolilao', 'Buhang', 'Buntatala',
        'Cabalawan', 'Caingin', 'Calajunan', 'Calaparan',
        'Calubihan', 'Calumpang', 'Cansojong',
        'Cuartero', 'Cubay Norte', 'Cubay Sur',
        'Dampog', 'Dulonan', 'Dungon',
        'El 98 (Jaro)', 'Fajara', 'Gua-an',
        'Hilom', 'Hinactaanan', 'Humatagon',
        'Ibilao', 'Jaro Proper', 'Jereos',
        'Lagamit', 'Lanot', 'Lawi',
        'Leon Kilat', 'Libertad', 'Libongcogon',
        'Lico', 'Linao', 'Lopez Jaena',
        'Luna', 'Maasin', 'Macalbang', 'Magsaysay',
        'Malunggay', 'Managopaya', 'Mansaya',
        'Maria Cristina', 'Mariano Marcos',
        'Nasipit', 'Navais', 'Niño Jesus',
        'Nuevo','Obrero','Odiong',
        'Pale', 'Palhi', 'Pamul-ogan',
        'Panagtaran', 'Pepita', 'Poblacion Jaro',
        'Quinagaringan', 'Rizal', 'Roxas Village',
        'Sambag', 'San Isidro', 'San Nicolas',
        'San Pedro', 'Santo Domingo', 'Seminario',
        'Siena', 'Simon Ledesma', 'Sinubung',
        'Tabuc Suba', 'Taal', 'Tabucan',
        'Tagbac', 'Tigum', 'Ungka I', 'Ungka II',
        'Veterans Village', 'Yulo', 'Zamora',
    ],
    'mandurriao': [
        'Airport (Mandurriao)', 'Arguelles', 'Arsenal Aduana',
        'Ateneo', 'Bantud', 'Batan',
        'Bayuc', 'Boulevard', 'Calahunan',
        'Calumpang', 'Campo Alegre', 'Casambalangan',
        'Cock', 'Compañia', 'Cruz',
        'Cubay', 'Divinagracia', 'Don Esteban-Lapuz',
        'Dungon A', 'Dungon B', 'Dungon C',
        'Fajardo', 'Flores', 'General Hughes',
        'Hibao-an', 'Ibilao', 'Ingore',
        'Jaro', 'Kahirup', 'Kauswagan',
        'La Paz', 'Lawa-an', 'Leon',
        'Libertad', 'Linao', 'Lopez Jaena',
        'Luna', 'Mabolo', 'Magsaysay',
        'Mahina', 'Mandurriao Proper', 'Mansaya',
        'Maria', 'Mc Arthur', 'Molo',
        'Motorpool', 'Nabitasan', 'Navais',
        'Nonoy', 'Pana', 'Pobla Norte',
        'Pobla Sur', 'Quezon', 'Quintas',
        'Quirino', 'Roses', 'Roxas',
        'Sambag', 'San Agustin', 'San Felix',
        'San Isidro', 'San Jose', 'San Nicolas',
        'San Pedro', 'Santa Cruz', 'Santo Tomas',
        'Simon Ledesma', 'Sooc', 'Taal',
        'Tabuc Suba', 'Tabucan', 'Tagbac',
        'Tandoc', 'Tigum', 'Tiwi',
        'Ungka', 'Veterans', 'Yulo',
    ],
    'molo': [
        'Barangay I (Molo)', 'Barangay II (Molo)', 'Barangay III (Molo)',
        'Barangay IV (Molo)', 'Barangay V (Molo)', 'Barangay VI (Molo)',
        'Baybay Tanza', 'Bonifacio-Tanza', 'Burgos-Mabini-Plaza',
        'Calle Ledesma', 'Calle Real', 'Compania',
        'Concepcion', 'Cruz', 'Danao',
        'Delgado', 'Demo', 'Desamparados',
        'East Baluarte', 'East Timawa', 'Edganzon',
        'Fajardo', 'Flores', 'General Hughes',
        'Gloria', 'Gustilo', 'Habog-Habog Salvacion',
        'Hibao-an', 'Hinactaanan', 'Infante',
        'Ingore', 'Kahirup', 'La Paz',
        'Libertad', 'Linog', 'Lopez Jaena',
        'Luna', 'Mabolo', 'Magdalo',
        'Magsaysay', 'Molo Boulevard', 'Molo Proper',
        'Montinola', 'Motorpool', 'Nabitasan',
        'Navais', 'Nelly Garden', 'Nonoy',
        'North Baluarte', 'North Fundidor', 'North San Jose',
        'Obrero', 'Oñate De Leon', 'Ortiz',
        'Osmeña', 'Our Lady of Fatima', 'Our Lady of Lourdes',
        'Pablo Lavezares', 'Pena-Gomburza', 'People\'s Park',
        'Progreso', 'Punong', 'Quezon',
        'Quintin Salas', 'Railway', 'Remu',
        'Rizal', 'Rojas', 'San Agustin',
        'San Felix', 'San Isidro', 'San Jose',
        'San Pedro', 'Santa Cruz', 'Santa Filomena',
        'Santa Isabel', 'Santa Remedios', 'Santa Rosa',
        'Santo Domingo', 'Santo Niño Norte', 'Santo Niño Sur',
        'Santos Escario', 'Seminario', 'Simon Ledesma',
        'South Baluarte', 'South Fundidor', 'South San Jose',
        'Taal', 'Tabuc Suba', 'Taytay',
        'Ticud', 'Timawa Tanza', 'Veterans Village',
        'Villa Anita', 'West Habog-Habog', 'West Timawa',
        'Yulo Drive', 'Zamora-Melliza',
    ],
    'arevalo': [
        'Aguinaldo', 'Alimodian', 'Ang Ngipon',
        'Arevalo Proper', 'Arsenal', 'Ateneo',
        'Badiang', 'Balabago', 'Balantang',
        'Baldoza', 'Batan', 'Bitoon',
        'Bolilao', 'Bonifacio', 'Buhang',
        'Cabalawan', 'Caingin', 'Calajunan',
        'Calaparan', 'Calubihan', 'Calumpang',
        'Cock', 'Compañia', 'Cruz',
        'Cubay', 'Dampog', 'Divinagracia',
        'Don Esteban', 'Dulonan', 'Dungon',
        'El 98', 'Fajara', 'Flores',
        'Gua-an', 'Hilom', 'Humatagon',
        'Ibilao', 'Ingore', 'Jaro',
        'La Paz', 'Lagamit', 'Lanot',
        'Lawi', 'Leon Kilat', 'Libertad',
        'Libongcogon', 'Lico', 'Linao',
        'Lopez Jaena', 'Luna', 'Maasin',
        'Macalbang', 'Magsaysay', 'Malunggay',
        'Managopaya', 'Mansaya', 'Maria Cristina',
        'Nasipit', 'Navais', 'Nino Jesus',
        'Nuevo', 'Obrero', 'Odiong',
        'Pale', 'Palhi', 'Pamul-ogan',
        'Panagtaran', 'Pepita', 'Quinagaringan',
        'Rizal', 'Roxas Village', 'Sambag',
        'San Isidro', 'San Nicolas', 'San Pedro',
        'Santo Domingo', 'Seminario', 'Siena',
        'Simon Ledesma', 'Sinubung', 'Tabuc Suba',
        'Taal', 'Tabucan', 'Tagbac',
        'Tigum', 'Ungka', 'Veterans Village',
        'Yulo', 'Zamora',
    ],
    'lapuz': [
        'Arguelles', 'Arsenal Aduana', 'Balabago',
        'Balantang', 'Bantud', 'Batan',
        'Bayuc', 'Bitoon', 'Bolilao',
        'Buhang', 'Buntatala', 'Cabalawan',
        'Caingin', 'Calajunan', 'Calaparan',
        'Calubihan', 'Cansojong', 'Cruz',
        'Dampog', 'Don Esteban-Lapuz', 'Dulonan',
        'Dungon A', 'Dungon B', 'El 98',
        'Fajardo', 'Flores', 'General Hughes',
        'Gua-an', 'Hibao-an Norte', 'Hibao-an Sur',
        'Hilom', 'Humatagon', 'Ibilao',
        'Ingore', 'Kahirup', 'Lagamit',
        'Lanit', 'Lanot', 'Lapuz Norte',
        'Lapuz Sur', 'Lawi', 'Leon Kilat',
        'Libertad', 'Libongcogon', 'Lico',
        'Linao', 'Lopez Jaena Norte', 'Lopez Jaena Sur',
        'Luna', 'M. V. Hechanova', 'Maasin',
        'Macalbang', 'Magsaysay', 'Malunggay',
        'Managopaya', 'Mansaya-Lapuz', 'Motorpool',
        'Nabitasan', 'Nasipit', 'Navais',
        'Nonoy', 'Obrero-Lapuz', 'Odiong',
        'Pale', 'Palhi', 'Pamul-ogan',
        'Panagtaran', 'Pepita', 'Progreso-Lapuz',
        'Punong-Lapuz', 'Quinagaringan', 'Remu-Lapuz',
        'Rizal', 'Roxas Village', 'Sambag',
        'San Isidro', 'San Nicolas', 'San Pedro',
        'Sinikway', 'Sinubung', 'Tabuc Suba',
        'Taal', 'Tabucan', 'Tagbac',
        'Tigum', 'Ungka I', 'Ungka II',
        'Veterans Village', 'Yulo', 'Zamora',
    ],
}

# District adjacency map
DISTRICT_ADJACENCY = {
    'city_proper': {'jaro', 'lapuz', 'molo'},
    'jaro':        {'city_proper', 'mandurriao'},
    'molo':        {'city_proper', 'arevalo'},
    'mandurriao':  {'jaro', 'lapuz'},
    'arevalo':     {'molo', 'lapuz'},
    'lapuz':       {'city_proper', 'mandurriao', 'arevalo'},
}

# Build reverse lookup: barangay_name (lowercase) → district
_BARANGAY_TO_DISTRICT = {}
for district, barangays in ILOILO_DISTRICTS.items():
    for b in barangays:
        _BARANGAY_TO_DISTRICT[b.lower()] = district


def get_district(barangay_name):
    """Returns the district for a barangay name, or None if not found."""
    if not barangay_name:
        return None
    return _BARANGAY_TO_DISTRICT.get(barangay_name.strip().lower())


def score_location(job, profile):
    """
    Returns a location boost between 0.0 and 1.0 based on proximity.

    Scoring tiers:
    - Remote job → 1.0 for everyone
    - Overseas job → 0.0 (no location boost)
    - Jobseeker outside Iloilo Province → 0.05
    - Jobseeker in Iloilo Province but not Iloilo City → 0.20
    - Jobseeker in Iloilo City, different district, not adjacent → 0.40
    - Jobseeker in Iloilo City, adjacent district → 0.65
    - Jobseeker in Iloilo City, same district → 0.85
    - Exact same barangay → 1.0
    """
    # Remote jobs are accessible to everyone
    if job.location_type == 'remote':
        return 1.0

    # Overseas jobs — location score not applicable
    if job.location_type == 'overseas':
        return 0.0

    # Jobseeker outside Iloilo Province
    jobseeker_province = getattr(profile, 'province', '').strip().lower()
    if jobseeker_province and 'iloilo' not in jobseeker_province:
        return 0.05

    # Jobseeker in Iloilo Province but not Iloilo City
    jobseeker_city = getattr(profile, 'city_municipality', '').strip().lower()
    if 'iloilo city' not in jobseeker_city and 'iloilo' in jobseeker_province:
        return 0.20

    # Both are in Iloilo City — use district comparison
    jobseeker_barangay = getattr(profile, 'barangay', '').strip()
    job_barangay = getattr(job, 'barangay_name', '').strip()

    # Exact barangay match
    if jobseeker_barangay and job_barangay:
        if jobseeker_barangay.lower() == job_barangay.lower():
            return 1.0

    jobseeker_district = get_district(jobseeker_barangay)
    job_district = get_district(job_barangay)

    if not jobseeker_district or not job_district:
        # Can't determine district — give a neutral mid score
        return 0.40

    # Same district
    if jobseeker_district == job_district:
        return 0.85

    # Adjacent district
    if job_district in DISTRICT_ADJACENCY.get(jobseeker_district, set()):
        return 0.65

    # Different, non-adjacent district
    return 0.40


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

    if not req.course_degree:
        return 1.0

    qualifying_educations = [
        edu for edu in educations
        if edu.level in LEVEL_ORDER and LEVEL_ORDER.index(edu.level) >= req_index
    ]

    for edu in qualifying_educations:
        if edu.course_degree and fuzzy_match(req.course_degree, edu.course_degree):
            return 1.0

    return 0.6


def score_experience(job, profile):
    try:
        req = job.experience_requirement
    except Exception:
        return 1.0

    required_months = req.months_required
    if required_months == 0:
        return 1.0

    experiences = WorkExperience.objects.filter(profile=profile)
    if not experiences.exists():
        return 0.0

    total_months = 0
    for exp in experiences:
        if exp.year_started:
            try:
                start_y = int(exp.year_started)
                if exp.is_current:
                    from datetime import date
                    end_y = date.today().year
                elif exp.year_ended:
                    end_y = int(exp.year_ended)
                else:
                    end_y = start_y
                total_months += max(0, (end_y - start_y) * 12)
            except (ValueError, TypeError):
                pass

    duration_score = min(1.0, total_months / required_months) if required_months > 0 else 1.0

    if req.any_experience_accepted or not req.preferred_position.strip():
        return round(duration_score, 2)

    jobseeker_positions = [exp.position for exp in experiences if exp.position]
    position_matched = any(
        fuzzy_match(req.preferred_position, pos)
        for pos in jobseeker_positions
    )

    if duration_score >= 1.0 and position_matched:
        return 1.0
    elif duration_score >= 1.0 and not position_matched:
        return 0.0
    elif duration_score < 1.0 and position_matched:
        return round(duration_score * 0.8, 2)
    else:
        return 0.0


def score_skills(job, profile):
    required_skills = job.skill_requirements.filter(is_required=True)
    jobseeker_skills = [s.name for s in Skill.objects.filter(profile=profile)]

    if not jobseeker_skills:
        return 0.0

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

    return round(required_score, 2)


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

    if best_ratio < FUZZY_THRESHOLD:
        return 0.0

    boost = ((best_ratio - FUZZY_THRESHOLD) / (100 - FUZZY_THRESHOLD)) * QUERY_BOOST_MAX
    return round(boost, 3)


def score_sector_match(job, profile):
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

    query_boost = score_query_boost(job, profile)
    location_raw = score_location(job, profile)
    location_boost = round(location_raw * LOCATION_BOOST_MAX, 3)

    total = min(1.0, base_score + query_boost + location_boost)

    # ── Counts for tooltip display ──
    required_skills = job.skill_requirements.filter(is_required=True)
    jobseeker_skills = [s.name for s in Skill.objects.filter(profile=profile)]
    matched_skills = sum(
        1 for rs in required_skills
        if any(fuzzy_match(rs.name, js) for js in jobseeker_skills)
    )

    required_certs = job.certification_requirements.filter(is_required=True)
    jobseeker_certs = [c.name for c in Certification.objects.filter(profile=profile)]
    matched_certs = sum(
        1 for rc in required_certs
        if any(fuzzy_match(rc.name, jc) for jc in jobseeker_certs)
    )

    try:
        req_months = job.experience_requirement.months_required
    except Exception:
        req_months = 0

    experiences = WorkExperience.objects.filter(profile=profile)
    total_months = 0
    for exp_obj in experiences:
        if exp_obj.year_started:
            try:
                start_y = int(exp_obj.year_started)
                if exp_obj.is_current:
                    from datetime import date
                    end_y = date.today().year
                elif exp_obj.year_ended:
                    end_y = int(exp_obj.year_ended)
                else:
                    end_y = start_y
                total_months += max(0, (end_y - start_y) * 12)
            except (ValueError, TypeError):
                pass

    jobseeker_district = get_district(getattr(profile, 'barangay', ''))
    job_district = get_district(getattr(job, 'barangay_name', ''))

    return {
        'total': round(total * 100),
        'breakdown': {
            'skills': round(skills * 100),
            'education': round(edu * 100),
            'experience': round(exp * 100),
            'certifications': round(certs * 100),
            'query_boost': round(query_boost * 100),
            'location_boost': round(location_boost * 100),
        },
        'counts': {
            'skills_matched': matched_skills,
            'skills_total': required_skills.count(),
            'education_met': edu >= 1.0,
            'experience_months': total_months,
            'experience_required': req_months,
            'certs_matched': matched_certs,
            'certs_total': required_certs.count(),
        },
        'location': {
            'jobseeker_district': jobseeker_district,
            'job_district': job_district,
            'score': round(location_raw * 100),
        },
        'sector_match': score_sector_match(job, profile),
    }


def get_ranked_jobseekers(job, sector_filter=False):
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

    query = getattr(profile, 'job_search_query', '').strip()
    if query:
        from rapidfuzz import fuzz as _fuzz
        def matches_query(item):
            targets = [
                item['job'].title,
                item['job'].description,
            ] + [s.name for s in item['job'].skill_requirements.all()]
            best = max(
                _fuzz.token_set_ratio(query.lower(), t.lower())
                for t in targets if t
            )
            return best >= FUZZY_THRESHOLD

        preferred = [r for r in results if matches_query(r)]
        others = [r for r in results if not matches_query(r)]
        preferred.sort(key=lambda x: x['score'], reverse=True)
        others.sort(key=lambda x: x['score'], reverse=True)
        results = preferred + others
    else:
        results.sort(key=lambda x: x['score'], reverse=True)

    return results