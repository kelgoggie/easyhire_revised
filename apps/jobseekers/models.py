from django.db import models
from apps.accounts.models import User


class Sector(models.Model):
    FRESH_GRADUATE = "fresh_graduate"
    LGBTQIA = "lgbtqia"
    OSY = "osy"
    PWD = "pwd"
    SENIOR = "senior_citizen"
    SOLO_PARENT = "solo_parent"
    TESDA = "tesda_graduate"

    SECTOR_CHOICES = [
        (FRESH_GRADUATE, "Fresh Graduate"),
        (LGBTQIA, "LGBTQIA++"),
        (OSY, "Out-of-School Youth (OSY)"),
        (PWD, "Persons with Disabilities (PWD)"),
        (SENIOR, "Senior Citizen"),
        (SOLO_PARENT, "Solo Parent"),
        (TESDA, "TESDA Graduate"),
    ]

    code = models.CharField(max_length=50, choices=SECTOR_CHOICES, unique=True)
    label = models.CharField(max_length=100)

    class Meta:
        db_table = "sectors"

    def __str__(self):
        return self.label


class JobseekerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="jobseeker_profile")
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    suffix = models.CharField(max_length=20, blank=True)
    sex = models.CharField(max_length=10, choices=[("M", "Male"), ("F", "Female")])
    date_of_birth = models.DateField(null=True, blank=True)
    civil_status = models.CharField(max_length=30, blank=True)
    house_unit = models.CharField(max_length=100, blank=True)
    street_barangay = models.CharField(max_length=200)
    city_municipality = models.CharField(max_length=100, default="Iloilo City")
    province = models.CharField(max_length=100, default="Iloilo")
    province_code = models.CharField(max_length=20, blank=True)
    city_code = models.CharField(max_length=20, blank=True)
    barangay_code = models.CharField(max_length=20, blank=True)
    barangay = models.CharField(max_length=200, blank=True)
    contact_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20)
    job_search_query = models.CharField(max_length=255, blank=True)
    sectors = models.ManyToManyField(Sector, blank=True, related_name="jobseekers")
    followed_companies = models.ManyToManyField(
        "employers.Company", blank=True, related_name="followers"
    )
    profile_complete = models.BooleanField(default=False)
    profile_visibility = models.CharField(max_length=20, default='public')
    sector_badge_visibility = models.CharField(max_length=20, default='public')
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    bio = models.TextField(blank=True)

    class Meta:
        db_table = "jobseeker_profiles"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name, self.suffix]
        return " ".join(p for p in parts if p)

    def can_show_badges_to(self, company):
        """Whether this jobseeker's sector badges should be shown to a given employer.

        Honors the user's `sector_badge_visibility` preference:
          - 'public'  : always show
          - 'similar' : show only when this profile shares at least one sector with the company
          - 'hidden'  : never show
        """
        v = self.sector_badge_visibility
        if v == 'hidden':
            return False
        if v == 'similar':
            mine  = set(self.sectors.values_list('id', flat=True))
            theirs = set(company.sector_badges.values_list('id', flat=True)) if company else set()
            return bool(mine & theirs)
        return True  # 'public' (default) or any unrecognized value


class Education(models.Model):
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

    profile = models.ForeignKey(JobseekerProfile, on_delete=models.CASCADE, related_name="educations")
    level = models.CharField(max_length=30, choices=LEVELS)
    course_degree = models.CharField(max_length=200, blank=True)
    institution = models.CharField(max_length=200, blank=True)
    year_started = models.PositiveIntegerField(null=True, blank=True)
    year_ended = models.PositiveIntegerField(null=True, blank=True)
    is_current = models.BooleanField(default=False,
        help_text="I'm still attending this institution.")

    class Meta:
        db_table = "jobseeker_educations"


class Certification(models.Model):
    profile = models.ForeignKey(JobseekerProfile, on_delete=models.CASCADE, related_name="certifications")
    name = models.CharField(max_length=200)
    issuing_org = models.CharField(max_length=200, blank=True)
    year_received = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "jobseeker_certifications"


class Skill(models.Model):
    profile = models.ForeignKey(JobseekerProfile, on_delete=models.CASCADE, related_name="skills")
    name = models.CharField(max_length=200)

    class Meta:
        db_table = "jobseeker_skills"


class WorkExperience(models.Model):
    profile = models.ForeignKey(JobseekerProfile, on_delete=models.CASCADE, related_name="experiences")
    position = models.CharField(max_length=200)
    company = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    month_started = models.CharField(max_length=20, blank=True)
    year_started = models.PositiveIntegerField(null=True, blank=True)
    month_ended = models.CharField(max_length=20, blank=True)
    year_ended = models.PositiveIntegerField(null=True, blank=True)
    is_current = models.BooleanField(default=False,
        help_text="I'm still employed under this position.")
    # Set when this entry was auto-created from a Hired application on EasyHire.
    # Lets us update / end the entry when the employer un-hires.
    from_application = models.ForeignKey(
        'jobs.Application', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='work_experiences',
    )

    class Meta:
        db_table = "jobseeker_experiences"


class PersonalInfoChangeRequest(models.Model):
    """Jobseeker-submitted edit to their core personal info, pending PESO review."""
    STATUS_PENDING  = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING,  "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    profile       = models.ForeignKey(JobseekerProfile, on_delete=models.CASCADE, related_name="info_change_requests")
    first_name    = models.CharField(max_length=100)
    middle_name   = models.CharField(max_length=100, blank=True, default="")
    last_name     = models.CharField(max_length=100)
    suffix        = models.CharField(max_length=20,  blank=True, default="")
    date_of_birth = models.DateField(null=True, blank=True)
    sex           = models.CharField(max_length=10,  blank=True, default="")
    id_document   = models.FileField(upload_to='personal_info_ids/', null=True, blank=True,
        help_text="Uploaded photo/scan of a valid Philippine ID for PESO verification.")
    id_type       = models.CharField(max_length=50, blank=True, default='',
        help_text="Optional — admin notes which ID type was provided. The jobseeker no longer picks this; they just upload.")
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    submitted_at  = models.DateTimeField(auto_now_add=True)
    reviewed_at   = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "personal_info_change_requests"
        ordering = ["-submitted_at"]

    def __str__(self):
        return f"{self.profile} change request ({self.status})"


class JobInteraction(models.Model):
    LIKED = "liked"
    HIDDEN = "hidden"

    TYPE_CHOICES = [
        (LIKED, "Liked"),
        (HIDDEN, "Hidden"),
    ]

    jobseeker = models.ForeignKey(JobseekerProfile, on_delete=models.CASCADE, related_name="job_interactions")
    job = models.ForeignKey("jobs.JobPosting", on_delete=models.CASCADE, related_name="jobseeker_interactions")
    interaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "jobseeker_job_interactions"
        unique_together = ("jobseeker", "job")