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

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    def is_hard_to_fill(self):
        """Used by analytics: open for 30+ days with fewer than 3 applicants."""
        from django.utils import timezone
        from datetime import timedelta
        age = timezone.now() - self.created_at
        applicant_count = self.jobseeker_interactions.filter(
            interaction_type="liked"
        ).count()
        return (
            self.status == self.STATUS_OPEN
            and age > timedelta(days=30)
            and applicant_count < 3
        )


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

    job = models.OneToOneField(
        JobPosting, on_delete=models.CASCADE, related_name="education_requirement"
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
        if self.months_required == 0:
            return "No experience required"
        years = self.months_required // 12
        months = self.months_required % 12
        parts = []
        if years:
            parts.append(f"{years} year{'s' if years != 1 else ''}")
        if months:
            parts.append(f"{months} month{'s' if months != 1 else ''}")
        return ", ".join(parts)


class Application(models.Model):
    STATUS_PENDING = "pending"
    STATUS_ACCEPTED = "accepted"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
    ]

    jobseeker = models.ForeignKey(
        "jobseekers.JobseekerProfile", on_delete=models.CASCADE,
        related_name="applications"
    )
    job = models.ForeignKey(
        JobPosting, on_delete=models.CASCADE,
        related_name="applications"
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "applications"
        unique_together = ("jobseeker", "job")

    def __str__(self):
        return f"{self.jobseeker} → {self.job}"