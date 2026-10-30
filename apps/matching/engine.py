from rapidfuzz import fuzz
from apps.jobseekers.models import Education, Skill, Certification, WorkExperience, Project, Extracurricular


WEIGHT_SKILLS = 0.40
WEIGHT_EDUCATION = 0.25
WEIGHT_EXPERIENCE = 0.25
WEIGHT_CERTIFICATIONS = 0.10


def get_weights(job=None):
    """Return the (skills, education, experience, certifications) weights
    to score `job` with.

    If `job` has its own JobMatchingWeights row with use_custom_weights=True,
    those take priority. Otherwise (no job passed, no override row, or the
    override is switched off) falls back to PESO's site-wide SiteSettings
    defaults — so every job that hasn't opted into custom weights keeps
    scoring exactly as it did before this feature existed.
    """
    if job is not None:
        try:
            jmw = job.matching_weights
        except Exception:
            jmw = None
        if jmw is not None and jmw.use_custom_weights:
            return (jmw.weight_skills, jmw.weight_education, jmw.weight_experience, jmw.weight_certifications)
    try:
        from apps.admin_panel.models import SiteSettings
        s = SiteSettings.get()
        return (s.weight_skills, s.weight_education, s.weight_experience, s.weight_certifications)
    except Exception:
        return (WEIGHT_SKILLS, WEIGHT_EDUCATION, WEIGHT_EXPERIENCE, WEIGHT_CERTIFICATIONS)

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
    if req is None:
        # job.education_requirement is a `.first()`-backed property (unlike
        # experience_requirement's OneToOneField, it returns None rather
        # than raising when the job has no education requirement row).
        return 1.0

    # "als" (Alternative Learning System) sits right after junior_high —
    # DepEd's ALS Accreditation & Equivalency track is the non-formal
    # equivalent of completing basic education, roughly on par with a
    # junior-high-level credential. There's no finer-grained "which ALS
    # level" data on the Education model to place it more precisely than
    # that; adjust this placement if PESO's actual policy differs.
    LEVEL_ORDER = [
        "elementary", "junior_high", "als", "senior_high", "vocational",
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

    required_positions = req.preferred_positions_list()
    if req.any_experience_accepted or not required_positions:
        return round(duration_score, 2)

    jobseeker_positions = [exp.position for exp in experiences if exp.position]
    # Employers can list multiple acceptable prior roles; a jobseeker with
    # experience in ANY of them qualifies. Fuzzy match on both axes so
    # spelling variants ("Sec." vs "Secretary") still hit.
    position_strength = 1.0 if any(
        fuzzy_match(req_pos, seeker_pos)
        for req_pos in required_positions
        for seeker_pos in jobseeker_positions
    ) else 0.0

    # Semantic fallback — no lexical title match, but a required position
    # might still conceptually match a seeker's title, the free-text
    # description of any of their roles, or a project/extracurricular
    # (e.g. required "Legal Secretary" vs a seeker titled "Paralegal
    # Assistant" whose description covers the same ground, or who ran
    # their school's Moot Court Society — zero shared words in the title
    # alone). Checked against every required position, best similarity wins.
    if position_strength == 0.0:
        candidates = (
            list(jobseeker_positions)
            + [exp.description for exp in experiences if exp.description]
            + _profile_extra_texts(profile)
        )
        candidates = [c for c in candidates if c]
        if candidates:
            try:
                from apps.jobseekers.nlp_service import semantic_rank
                best = 0.0
                for req_pos in required_positions:
                    matches = semantic_rank(req_pos, candidates, top_k=1, min_similarity=SEMANTIC_THRESHOLD)
                    if matches and matches[0][1] > best:
                        best = matches[0][1]
                position_strength = round(best, 2)
            except Exception:
                position_strength = 0.0

    # Same combination shape as before (full credit at full duration + a
    # real position match, 80%-of-duration credit at partial duration),
    # just driven by a continuous position_strength now instead of a
    # True/False — a lexical match still behaves exactly as before
    # (strength=1.0 reduces to the old formula), a semantic-only match
    # gets scaled by how confident that match actually is.
    multiplier = 1.0 if duration_score >= 1.0 else duration_score * 0.8
    return round(position_strength * multiplier, 2)


# Credit given when a required skill's name shows up in a jobseeker skill's
# DESCRIPTION but not in any name (e.g. seeker lists "Photoshop" with
# description "also handles basic Illustrator work" and the job requires
# Illustrator). Weaker signal than a name match — partial credit.
SKILL_DESCRIPTION_CREDIT = 0.5


# Semantic similarity floor for skills/experience. Lower than the 0.45 used
# for custom criteria — this compares short phrases (skill names, job
# titles) rather than full sentences, and this embedding model scores
# short-phrase pairs lower across the board even when clearly related
# ("Legal Secretary"/"Paralegal Assistant" ≈ 0.51, "Customer Service"/
# "Client Relations" ≈ 0.39) — genuinely unrelated short pairs sampled
# around 0.15-0.28, so 0.35 sits in the gap between the two.
SEMANTIC_THRESHOLD = 0.35


def _skill_match_strength(req_name: str, seeker_skills, extra_texts=None):
    """Return the strongest match strength for a required skill against a
    list of the seeker's (name, description) pairs, plus optional extra
    free-text evidence (project/extracurricular text — see
    _profile_extra_texts).

    - 1.0 → any seeker skill NAME fuzzy-matches the requirement.
    - SKILL_DESCRIPTION_CREDIT → no name match, but the requirement is
      literally mentioned in a skill description OR in extra_texts (fuzzy
      token_set_ratio ≥ threshold) — e.g. a project description that
      happens to name-drop the exact skill.
    - semantic similarity (0.0-1.0) → nothing lexical fired, but the
      requirement might mean the same thing as a skill name, a skill
      description, or a project/extracurricular the seeker wrote (e.g.
      required "Customer Service" vs a seeker skill named "Client
      Relations" — zero shared words). Checked against all of the above
      together, best score wins. Same embedding model as
      score_custom_criterion; degrades to 0.0 if the ML deps aren't
      installed on this host.
    - 0.0 → no evidence at all.
    """
    if not req_name:
        return 0.0
    seeker_skills = seeker_skills or []
    extra_texts = extra_texts or []
    for name, _ in seeker_skills:
        if fuzzy_match(req_name, name):
            return 1.0
    # Description fallback. Use token_set_ratio because descriptions are
    # sentence-shaped ("2 years using Adobe Illustrator on print ads") —
    # substring/whole-word doesn't cut it. Same fuzzy threshold as names
    # so the bar for a description hit is comparable. extra_texts (project/
    # extracurricular text) gets the same treatment as a skill description.
    req_l = req_name.lower()
    description_pool = [desc for _, desc in seeker_skills if desc] + list(extra_texts)
    for desc in description_pool:
        if desc and fuzz.token_set_ratio(req_l, desc.lower()) >= FUZZY_THRESHOLD:
            return SKILL_DESCRIPTION_CREDIT

    candidates = [name for name, _ in seeker_skills] + description_pool
    if candidates:
        try:
            from apps.jobseekers.nlp_service import semantic_rank
            matches = semantic_rank(req_name, candidates, top_k=1, min_similarity=SEMANTIC_THRESHOLD)
        except Exception:
            matches = []
        if matches:
            return round(matches[0][1], 2)
    return 0.0


def _seeker_skill_pairs(profile):
    """(name, description) tuples for every skill the profile has. One
    query, reused across name/description scoring so we don't re-hit the DB."""
    return [(s.name, s.description or '') for s in Skill.objects.filter(profile=profile)]


def _profile_extra_texts(profile):
    """Free-text evidence beyond skills/certs/experience that can still back
    up a skill, experience, or custom-criterion match: project titles +
    descriptions, extracurricular names/roles/descriptions. A project
    description like "Built a dashboard using React and Node.js" can
    surface a relevant skill even if the jobseeker never listed it as a
    skill directly. Checked at the same lexical-description and semantic
    tiers as skill descriptions — never a tier-1 (name) match on its own,
    since there's no "name" here comparable to a skill/cert name.

    One query per model, reused across every criterion's scoring call for
    this profile so callers don't re-hit the DB per required skill."""
    texts = []
    for p in Project.objects.filter(profile=profile):
        if p.title:
            texts.append(p.title)
        if p.description:
            texts.append(p.description)
    for e in Extracurricular.objects.filter(profile=profile):
        if e.name:
            texts.append(e.name)
        if e.role:
            texts.append(e.role)
        if e.description:
            texts.append(e.description)
    return texts


def score_skills(job, profile):
    required_skills = job.skill_requirements.filter(is_required=True)
    seeker_pairs = _seeker_skill_pairs(profile)
    extra_texts = _profile_extra_texts(profile)

    # A seeker with zero skills listed but rich projects/extracurriculars
    # can still earn credit via those — only bail if there's truly nothing
    # to check against.
    if not seeker_pairs and not extra_texts:
        return 0.0

    if required_skills.exists():
        # Sum of per-requirement strengths (each in [0,1]) divided by the
        # requirement count → same 0-1 range as before, but description
        # hits now nudge the score above 0.
        total_strength = sum(
            _skill_match_strength(rs.name, seeker_pairs, extra_texts) for rs in required_skills
        )
        required_score = total_strength / required_skills.count()
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


def score_custom_criterion(criterion, profile):
    """Score an employer-defined custom criterion (e.g. "Licensing") against
    a jobseeker. There's no dedicated jobseeker-side field for an arbitrary
    employer-typed requirement, so this checks everything we know about
    them in three tiers:
      1. Lexical — requirement matches a skill/certification NAME (strong
         signal, full credit) — same `fuzzy_match` as the rest of this file.
      2. Lexical — mentioned in a skill description, work experience, bio,
         project, or extracurricular (weaker signal, partial credit) —
         same two-tier pattern `_skill_match_strength` uses above.
      3. Semantic — nothing lexically overlapped, but the requirement might
         still mean the same thing as something the jobseeker wrote (e.g.
         "comfortable under pressure" vs. "thrives in a fast-paced
         environment" share zero words). Reuses the sentence-transformers
         model already loaded for autocomplete — degrades to 0.0 if the ML
         deps aren't installed on this host, same as everywhere else that
         touches nlp_service.

    Returns a 0.0-1.0 score.
    """
    requirement = (criterion.requirement_text or '').strip()
    if not requirement:
        return 1.0  # nothing to check against — don't penalize an empty requirement

    seeker_pairs = _seeker_skill_pairs(profile)
    cert_names = list(Certification.objects.filter(profile=profile).values_list('name', flat=True))

    # Strong signal — requirement matches a skill or certification NAME.
    for name, _ in seeker_pairs:
        if name and fuzzy_match(requirement, name):
            return 1.0
    for cert_name in cert_names:
        if cert_name and fuzzy_match(requirement, cert_name):
            return 1.0

    # Weaker signal — mentioned in a skill description, work experience,
    # bio, project, or extracurricular.
    longer_texts = [desc for _, desc in seeker_pairs if desc]
    for exp in WorkExperience.objects.filter(profile=profile):
        if exp.position:
            longer_texts.append(exp.position)
        if exp.description:
            longer_texts.append(exp.description)
    bio = getattr(profile, 'bio', '')
    if bio:
        longer_texts.append(bio)
    longer_texts += _profile_extra_texts(profile)

    req_l = requirement.lower()
    for text in longer_texts:
        if text and fuzz.token_set_ratio(req_l, text.lower()) >= FUZZY_THRESHOLD:
            return SKILL_DESCRIPTION_CREDIT

    # Semantic fallback — no shared words anywhere above, but the meaning
    # might still match. Compare against every text snippet we have (skill
    # names + the weaker-signal pool already built above) and take the
    # single best similarity as the score.
    candidates = [name for name, _ in seeker_pairs] + cert_names + longer_texts
    candidates = [c for c in candidates if c]
    if candidates:
        try:
            from apps.jobseekers.nlp_service import semantic_rank
            matches = semantic_rank(requirement, candidates, top_k=1, min_similarity=0.45)
        except Exception:
            matches = []
        if matches:
            return round(matches[0][1], 2)

    return 0.0


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

    w_skills, w_edu, w_exp, w_certs = get_weights(job)

    # ── Combine every active criterion — the 4 standard ones plus any     ──
    # employer-defined custom criteria on this job — into one weighted
    # average. Normalizing by the total weight (instead of assuming the
    # weights already sum to 1.0) means an employer's custom weights don't
    # have to add up perfectly, and a job with extra custom criteria just
    # dilutes the standard four proportionally rather than overweighting
    # the total. See JobMatchingWeights / JobCustomCriterion.
    criteria = [
        (skills, w_skills),
        (edu,    w_edu),
        (exp,    w_exp),
        (certs,  w_certs),
    ]
    custom_criteria = list(job.custom_criteria.all())
    custom_results = [(c, score_custom_criterion(c, profile)) for c in custom_criteria]
    criteria += [(c_score, c.weight) for c, c_score in custom_results]

    total_weight = sum(w for _, w in criteria)
    base_score = (sum(s * w for s, w in criteria) / total_weight) if total_weight > 0 else 0.0

    query_boost = score_query_boost(job, profile)
    location_raw = score_location(job, profile)
    location_boost = round(location_raw * LOCATION_BOOST_MAX, 3)

    total = min(1.0, base_score + query_boost + location_boost)

    # ── Counts for tooltip display ──
    required_skills = job.skill_requirements.filter(is_required=True)
    seeker_pairs = _seeker_skill_pairs(profile)
    extra_texts = _profile_extra_texts(profile)
    jobseeker_skills = [name for name, _ in seeker_pairs]
    # A skill counts as "matched" for the tooltip's "X of Y" line if we
    # found ANY evidence — name match, description mention, or a project/
    # extracurricular that covers it. Keeping the count boolean here so
    # the UI copy stays readable.
    matched_skills = sum(
        1 for rs in required_skills
        if _skill_match_strength(rs.name, seeker_pairs, extra_texts) > 0
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

    # ── Per-requirement match tags (rendered by _match_breakdown.html) ──
    # For each category we build a list of {name, met} entries derived
    # from the JOB's requirements — each item is coloured teal (met) or
    # gray (missing) in the template. Non-required rows are skipped so
    # employers only see must-haves.
    skill_items = [
        {'name': rs.name,
         'met': _skill_match_strength(rs.name, seeker_pairs, extra_texts) > 0}
        for rs in required_skills
    ]
    cert_items = [
        {'name': rc.name,
         'met': any(fuzzy_match(rc.name, jc) for jc in jobseeker_certs)}
        for rc in required_certs
    ]

    edu_items = []
    try:
        edu_req = job.education_requirement
    except Exception:
        edu_req = None
    if edu_req:
        edu_label = edu_req.get_level_display()
        if edu_req.course_degree:
            edu_label = f'{edu_label} — {edu_req.course_degree}'
        edu_items = [{'name': edu_label, 'met': edu >= 1.0}]

    exp_items = []
    try:
        exp_req = job.experience_requirement
    except Exception:
        exp_req = None
    if exp_req:
        try:
            exp_label = exp_req.display_experience
        except Exception:
            exp_label = f'{req_months} month{"" if req_months == 1 else "s"} experience'
        exp_items = [{'name': exp_label, 'met': exp >= 1.0}]

    # Employer-defined custom criteria (e.g. "Licensing") — kept as its own
    # list rather than flattened into the fixed keys above so existing
    # callers/templates reading breakdown['skills'] etc. are unaffected by
    # a job that has zero custom criteria (the list is just empty).
    custom_breakdown = [
        {'id': c.id, 'name': c.name, 'score': round(c_score * 100), 'weight': round(c.weight * 100)}
        for c, c_score in custom_results
    ]
    custom_items = [
        {'name': c.name, 'met': c_score >= 1.0, 'requirement_text': c.requirement_text}
        for c, c_score in custom_results
    ]

    return {
        'total': round(total * 100),
        'breakdown': {
            'skills': round(skills * 100),
            'education': round(edu * 100),
            'experience': round(exp * 100),
            'certifications': round(certs * 100),
            'query_boost': round(query_boost * 100),
            'location_boost': round(location_boost * 100),
            'custom': custom_breakdown,
        },
        'matched_items': {
            'skills':         skill_items,
            'education':      edu_items,
            'experience':     exp_items,
            'certifications': cert_items,
            'custom':         custom_items,
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
    # Honor privacy: hide deactivated accounts, and hide profiles that have
    # been tagged Hired anywhere when the user opted to disappear after-hire.
    hidden_after_hire_ids = (
        JobseekerProfile.objects
        .filter(profile_visibility='hidden', applications__status='hired')
        .values_list('id', flat=True).distinct()
    )
    jobseekers = (
        JobseekerProfile.objects
        .filter(profile_complete=True, user__is_active=True)
        .exclude(id__in=hidden_after_hire_ids)
    )
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
    jobs = JobPosting.objects.filter(status='open', deleted_at__isnull=True, admin_disabled=False).select_related(
        'company', 'experience_requirement', 'matching_weights'
    ).prefetch_related('skill_requirements', 'certification_requirements', 'education_requirements', 'custom_criteria')

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