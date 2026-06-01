from django.db import models
from apps.accounts.models import User


class Company(models.Model):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    DENIED = "verification_denied"
    VERIFIED = "verified"

    VERIFICATION_CHOICES = [
        (UNVERIFIED, "Unverified"),
        (PENDING, "Pending"),
        (DENIED, "Verification Denied"),
        (VERIFIED, "Verified"),
    ]

    # Core info — some fields locked after registration (only admin can change)
    name = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True)
    LOCAL = "local"
    OVERSEAS = "overseas"
    BPO = "bpo"

    COMPANY_TYPE_CHOICES = [
        (LOCAL, "Local"),
        (OVERSEAS, "Overseas"),
        (BPO, "BPO"),
]

    type_of_company = models.CharField(
        max_length=20, choices=COMPANY_TYPE_CHOICES,
        help_text="Determines which verification documents are required."
    )
    nature_of_company = models.CharField(max_length=200,
        help_text="e.g. School, University, Hospital, Retail. Free text with suggestions."
    )
    
    description = models.TextField(blank=True)
    company_size = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="company_logos/", null=True, blank=True)

    # Contact
    company_email = models.EmailField()
    recruitment_email = models.EmailField()

    # Main branch address (can be outside Iloilo)
    main_branch_address = models.CharField(max_length=300)

    # Iloilo branch address (required for PESO partnership)
    iloilo_bldg_unit = models.CharField(max_length=100, blank=True)
    iloilo_street = models.CharField(max_length=200, blank=True)
    iloilo_barangay_code = models.CharField(max_length=20, blank=True)
    iloilo_barangay_name = models.CharField(max_length=200, blank=True)
    iloilo_city = models.CharField(max_length=100, default="Iloilo City")
    iloilo_province = models.CharField(max_length=100, default="Iloilo")

    # Hiring sector badges — used in algorithm and displayed on profile
    sector_badges = models.ManyToManyField(
        "jobseekers.Sector", blank=True, related_name="companies"
    )

    # Verification
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_CHOICES, default=UNVERIFIED
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="verified_companies"
    )
    rejection_note = models.TextField(blank=True)

    # Set True for companies imported from PESO's existing database
    is_peso_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "companies"
        verbose_name_plural = "companies"

    def __str__(self):
        return self.name

    @property
    def is_verified(self):
        return self.verification_status == self.VERIFIED


class EmployerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="employer_profile")
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="representatives")

    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    suffix = models.CharField(max_length=20, blank=True)
    position = models.CharField(max_length=200,
        help_text="Representative's position/role in the company")
    sex = models.CharField(max_length=10, choices=[("M", "Male"), ("F", "Female")])
    birthday = models.DateField(null=True, blank=True)
    phone = models.CharField(max_length=20)
    email = models.EmailField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "employer_profiles"

    def __str__(self):
        return f"{self.first_name} {self.last_name} @ {self.company.name}"


class VerificationDocument(models.Model):
    # Documents required for all companies
    MAYORS_PERMIT = "mayors_permit"
    PHILJOBNET_ACCREDITATION = "philjobnet_accreditation"
    PHILJOBNET_DASHBOARD = "philjobnet_dashboard"
    JOB_VACANCIES_LIST = "job_vacancies_list"

    # Additional documents for manpower agencies
    PEA_LICENSE = "pea_license"
    DO174_CERTIFICATE = "do174_certificate"

    # Additional documents for overseas agencies only
    POEA_LICENSE = "poea_license"
    JOB_ORDER = "job_order"

    DOC_TYPE_CHOICES = [
        # All companies
        (MAYORS_PERMIT, "Business/Mayor's Permit"),
        (PHILJOBNET_ACCREDITATION, "PhilJobNet Proof of Accreditation"),
        (PHILJOBNET_DASHBOARD, "Screenshot of PhilJobNet Posting Dashboard"),
        (JOB_VACANCIES_LIST, "List of Job Vacancies"),
        # Manpower agencies (local and overseas)
        (PEA_LICENSE, "Private Employment Agency (PEA) License (DOLE)"),
        (DO174_CERTIFICATE, "D.O. 174 Series of 2017 Certificate (DOLE)"),
        # Overseas agencies only
        (POEA_LICENSE, "POEA Certificate of License"),
        (JOB_ORDER, "Approved Job Balance Order"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="verification_docs")
    doc_type = models.CharField(max_length=50, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to="employer_docs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "verification_documents"

    def __str__(self):
        return f"{self.get_doc_type_display()} — {self.company.name}"


class CandidateInteraction(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="candidate_interactions")
    jobseeker = models.ForeignKey("jobseekers.JobseekerProfile", on_delete=models.CASCADE, related_name="employer_interactions")
    job = models.ForeignKey("jobs.JobPosting", on_delete=models.CASCADE, related_name="employer_candidate_interactions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "candidate_interactions"
        unique_together = ("company", "jobseeker", "job")