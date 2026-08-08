from django.db import models


class JobPosting(models.Model):
    # Location type choices
    ILOILO = "iloilo"
    OVERSEAS = "overseas"
    REMOTE = "remote"

    LOCATION_TYPE_CHOICES = [
        (ILOILO, "Iloilo City"),
        (OVERSEAS, "Overseas"),
        (REMOTE, "Remote"),
    ]

    STATUS_OPEN = "open"
    STATUS_CLOSED = "closed"
    STATUS_DRAFT = "draft"

    STATUS_CHOICES = [
        (STATUS_OPEN, "Open"),
        (STATUS_CLOSED, "Closed"),
        (STATUS_DRAFT, "Draft"),
    ]

    # Who can see this posting.
    # - 'public'  → anyone (including anonymous visitors on marketing pages)
    # - 'members' → registered EasyHire users only; anon users get 404
    VISIBILITY_PUBLIC  = "public"
    VISIBILITY_MEMBERS = "members"
    VISIBILITY_CHOICES = [
        (VISIBILITY_PUBLIC,  "Public"),
        (VISIBILITY_MEMBERS, "Registered EasyHire Only"),
    ]

    company = models.ForeignKey(
        "employers.Company", on_delete=models.CASCADE, related_name="job_postings"
    )

    # Locked after creation
    title = models.CharField(max_length=300)

    # Location
    location_type = models.CharField(
        max_length=10, choices=LOCATION_TYPE_CHOICES, default=ILOILO
    )
    # Used when location_type is ILOILO
    bldg_unit = models.CharField(max_length=100, blank=True)
    street = models.CharField(max_length=200, blank=True)
    barangay_code = models.CharField(max_length=20, blank=True)
    barangay_name = models.CharField(max_length=200, blank=True)
    city = models.CharField(max_length=100, default="Iloilo City",
        help_text="Locked to Iloilo City for local jobs.")
    # Used when location_type is OVERSEAS
    overseas_address = models.CharField(max_length=300, blank=True)

    # Editable fields
    description = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_OPEN)
    slots = models.PositiveIntegerField(default=1)
    salary_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    salary_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Optional posting-level contact info (overrides company defaults if set)
    contact_email = models.EmailField(blank=True, default='')
    contact_phone = models.CharField(max_length=20, blank=True, default='')
    # Free-text bag of keywords used by the matching engine and search
    search_keywords = models.CharField(max_length=500, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Set when a PESO admin disables this posting. We piggy-back on the
    # 'closed' status (so the rest of the app keeps treating it as
    # not-acceptable) but the flag + reason let employer/admin UIs distinguish
    # an admin takedown from a voluntary close, and the employer can't
    # re-open it from their side once disabled.
    admin_disabled = models.BooleanField(default=False)
    admin_disabled_reason = models.TextField(blank=True, default='')

    # Soft-delete. When set, the job is in the employer's "Trash" tab and
    # excluded from every public / matching surface. A follow-up admin
    # purge action hard-deletes rows where deleted_at is older than 30
    # days. We keep Application rows through the purge by SET_NULL'ing
    # their .job so historical analytics (monthly applications, hires) stay
    # intact even after the JobPosting itself is gone.
    deleted_at = models.DateTimeField(null=True, blank=True)

    # Employers can record hires they made outside EasyHire (walk-ins,
    # referrals, other job boards) so the platform's stats reflect the true
    # fulfillment of the posting. Purely informational — doesn't decrement
    # slots or auto-close the job; the employer still uses the Close Job
    # action when the posting is fully filled.
    externally_hired_count = models.PositiveIntegerField(default=0)

    # Public vs members-only. Enforced in the two PublicJob* views by
    # excluding 'members' rows for anon visitors — logged-in users see
    # everything.
    visibility = models.CharField(
        max_length=10, choices=VISIBILITY_CHOICES, default=VISIBILITY_PUBLIC,
        help_text="Public jobs appear on the marketing site; members-only jobs are hidden from anonymous visitors.",
    )

    class Meta:
        db_table = "job_postings"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} @ {self.company.name}"

    @property
    def location_display(self):
        if self.location_type == self.REMOTE:
            return "Remote"
        if self.location_type == self.OVERSEAS:
            return self.overseas_address
        parts = [self.bldg_unit, self.street, self.barangay_name, self.city]
        return ", ".join(p for p in parts if p)

    @property
    def days_until_purge(self):
        """Days remaining before the admin's "Purge Trash" button can hard-
        delete this row. Returns None when the job isn't soft-deleted."""
        if not self.deleted_at:
            return None
        from django.utils import timezone
        from datetime import timedelta
        remaining = (self.deleted_at + timedelta(days=30)) - timezone.now()
        return max(0, remaining.days)

    # PESO's classification of licensed / regulated professions. Any of
    # these surfacing in a job title marks it as hard-to-fill for the
    # labor-market analytics view — these roles need PRC-licensed hires
    # so the applicant pool is inherently narrower.
    _LICENSED_PROFESSION_KEYWORDS = (
        'nurse', 'teacher', 'engineer', 'architect', 'doctor', 'lawyer',
        'pharmacist', 'accountant', 'midwife', 'physician', 'dentist',
        'optometrist', 'veterinarian', 'psychologist', 'radiologic',
        'physical therapist', 'occupational therapist',
        'medical technologist', 'med tech', 'criminologist',
        'social worker', 'surveyor', 'geologist', 'attorney',
    )
    # Certification names that signal a license/board-exam requirement.
    _LICENSE_CERT_KEYWORDS = ('prc', 'license', 'licence', 'board exam', 'let', ' cpa', ' rn ')

    @property
    def is_hard_to_fill(self):
        """PESO definition: jobs requiring high qualifications with
        licenses (registered nurse, teacher, engineer, etc.). Detected
        from the title's profession or from a license-shaped certification
        requirement — either signal alone is enough."""
        title = ' ' + (self.title or '').lower() + ' '
        if any(prof in title for prof in self._LICENSED_PROFESSION_KEYWORDS):
            return True
        try:
            for cert in self.certification_requirements.all():
                n = ' ' + (cert.name or '').lower() + ' '
                if any(k in n for k in self._LICENSE_CERT_KEYWORDS):
                    return True
        except Exception:
            pass
        return False

    @property
    def is_in_demand(self):
        """PESO definition: entry-level jobs (elementary / JHS / SHS
        education) that ask for 0-6 months of experience or none. These
        have the widest applicant pool and the shortest fill time — the
        "in demand" bucket in analytics.

        A job with NO stated education requirement still counts as in-demand
        as long as its experience ask is entry-level, since the effective
        floor is the same (anyone can apply)."""
        edu = self.education_requirement
        if edu and edu.level not in ('elementary', 'junior_high', 'senior_high'):
            return False
        try:
            exp = self.experience_requirement
            if exp and exp.months_required and exp.months_required > 6:
                return False
        except Exception:
            pass
        return True

    @property
    def education_requirement(self):
        """Backwards-compat alias: first education requirement, or None.

        The relation became one-to-many in migration 0002 so a single job
        can list multiple education paths (e.g. "BS Comp Sci OR Vocational
        TESDA"). Templates and matching code that access a single object
        keep working via this property; new code can iterate
        ``job.education_requirements.all()``.
        """
        return self.education_requirements.first()


class JobEducationRequirement(models.Model):
    LEVELS = [
        ("elementary", "Elementary"),
        ("junior_high", "High School / Junior High School"),
        ("senior_high", "Senior High School"),
        ("vocational", "Vocational / TESDA"),
        ("associate", "Associate Degree"),
        ("bachelor", "Bachelor's Degree"),
        ("master", "Master's Degree"),
        ("doctorate", "Doctorate"),
    ]

    job = models.ForeignKey(
        JobPosting, on_delete=models.CASCADE, related_name="education_requirements"
    )
    level = models.CharField(max_length=30, choices=LEVELS)
    course_degree = models.CharField(max_length=200, blank=True,
        help_text="Optional — e.g. 'BS Computer Science'. Leave blank to accept any course.")

    class Meta:
        db_table = "job_education_requirements"

    def __str__(self):
        return f"{self.get_level_display()} — {self.job.title}"


class JobSkillRequirement(models.Model):
    job = models.ForeignKey(
        JobPosting, on_delete=models.CASCADE, related_name="skill_requirements"
    )
    name = models.CharField(max_length=200)
    is_required = models.BooleanField(default=True,
        help_text="Required vs preferred — affects weighting in the algorithm.")

    class Meta:
        db_table = "job_skill_requirements"

    def __str__(self):
        return f"{self.name} ({'Required' if self.is_required else 'Preferred'})"


class JobCertificationRequirement(models.Model):
    job = models.ForeignKey(
        JobPosting, on_delete=models.CASCADE, related_name="certification_requirements"
    )
    name = models.CharField(max_length=200)
    issuing_org = models.CharField(max_length=200, blank=True)
    is_required = models.BooleanField(default=True)

    class Meta:
        db_table = "job_certification_requirements"

    def __str__(self):
        return f"{self.name} — {self.job.title}"


class JobExperienceRequirement(models.Model):
    job = models.OneToOneField(
        JobPosting, on_delete=models.CASCADE, related_name="experience_requirement"
    )
    months_required = models.PositiveIntegerField(default=0,
        help_text="Minimum months of experience required. Set to 0 for no experience needed.")
    description = models.TextField(blank=True,
        help_text="Optional detail — e.g. 'at least 6 months in a retail environment'.")
    any_experience_accepted = models.BooleanField(default=True,
        help_text="If selected, any work experience counts as long as duration is met.")
    preferred_position = models.CharField(max_length=200, blank=True,
        help_text="Preferred previous position/role. Used for fuzzy matching if any_experience_accepted is False.")


    class Meta:
        db_table = "job_experience_requirements"

    def __str__(self):
        return f"{self.display_experience} — {self.job.title}"

    @property
    def display_experience(self):
        """Duration + field qualifier, ready for a single-line tag.
        Examples:
          "No experience required"
          "6 months — any field"
          "6 months — Legal Secretary"
          "2 years — Legal Secretary or Paralegal (+2 more)"
        """
        if self.months_required == 0:
            return "No experience required"
        years = self.months_required // 12
        months = self.months_required % 12
        parts = []
        if years:
            parts.append(f"{years} year{'s' if years != 1 else ''}")
        if months:
            parts.append(f"{months} month{'s' if months != 1 else ''}")
        duration = ", ".join(parts)
        qualifier = self.experience_field_display
        return f"{duration} — {qualifier}" if qualifier else duration

    def preferred_positions_list(self):
        """Split the comma-separated `preferred_position` string into a
        clean list. Employers can list multiple acceptable prior roles
        (e.g. "Legal Secretary, Paralegal, Executive Assistant") and a
        jobseeker with experience in ANY of them qualifies."""
        raw = (self.preferred_position or '').strip()
        if not raw:
            return []
        seen, out = set(), []
        for part in raw.split(','):
            p = part.strip()
            key = p.lower()
            if p and key not in seen:
                seen.add(key)
                out.append(p)
        return out

    @property
    def experience_field_display(self):
        """Short qualifier for the experience tag: 'any field', a single
        position name, or 'X or Y' / 'X or Y (+N more)' for multiples.
        Returns '' when no experience is required — the caller can then
        skip the qualifier entirely."""
        if self.months_required == 0:
            return ''
        if self.any_experience_accepted:
            return 'any field'
        positions = self.preferred_positions_list()
        if not positions:
            return 'any field'
        if len(positions) == 1:
            return positions[0]
        if len(positions) == 2:
            return f'{positions[0]} or {positions[1]}'
        return f'{positions[0]} or {positions[1]} (+{len(positions) - 2} more)'


class Application(models.Model):
    STATUS_PENDING      = "pending"        # employer hasn't opened the application yet
    STATUS_VIEWED       = "viewed"         # employer opened it but hasn't decided
    STATUS_ACCEPTED     = "accepted"       # employer has decided to proceed; messaging is now enabled
    STATUS_REJECTED     = "rejected"       # terminal — no undo
    STATUS_HIRE_PENDING = "hire_pending"   # employer offered to hire; awaiting jobseeker accept/decline
    STATUS_HIRED        = "hired"          # terminal — applicant was tagged hired and confirmed

    # Labels are what `get_status_display()` returns. The "accepted" DB value
    # is rendered as "In Progress" so the UI matches the Proceed-then-message
    # flow on the employer side (employer is in progress with the candidate;
    # next step is interview / requirements / hire offer).
    STATUS_CHOICES = [
        (STATUS_PENDING,      "Pending"),
        (STATUS_VIEWED,       "Viewed"),
        (STATUS_ACCEPTED,     "In Progress"),
        (STATUS_REJECTED,     "Rejected"),
        (STATUS_HIRE_PENDING, "Hire Offered"),
        (STATUS_HIRED,        "Hired"),
    ]

    jobseeker = models.ForeignKey(
        "jobseekers.JobseekerProfile", on_delete=models.CASCADE,
        related_name="applications"
    )
    # SET_NULL (not CASCADE) so applications survive if the underlying
    # JobPosting is eventually purged after soft-delete. Analytics that
    # count applications / hires by month run off timestamps on this row
    # and don't need the JobPosting to exist anymore.
    job = models.ForeignKey(
        JobPosting, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="applications"
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default=STATUS_PENDING)
    message = models.TextField(blank=True, default='', db_column='application_message')
    created_at = models.DateTimeField(auto_now_add=True)
    # Set when the employer marks the applicant as Hired.
    hired_at = models.DateTimeField(null=True, blank=True)
    # Optional: employer can later mark when the employment ended. Null = still employed.
    employed_until = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "applications"
        unique_together = ("jobseeker", "job")

    def __str__(self):
        return f"{self.jobseeker} → {self.job}"