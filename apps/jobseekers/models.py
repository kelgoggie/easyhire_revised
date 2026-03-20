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
    phone = models.CharField(max_length=20)
    job_search_query = models.CharField(max_length=255, blank=True)
    sectors = models.ManyToManyField(Sector, blank=True, related_name="jobseekers")
    followed_companies = models.ManyToManyField(
        "employers.Company", blank=True, related_name="followers"
    )
    profile_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "jobseeker_profiles"

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name, self.suffix]
        return " ".join(p for p in parts if p)


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

    class Meta:
        db_table = "jobseeker_experiences"


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