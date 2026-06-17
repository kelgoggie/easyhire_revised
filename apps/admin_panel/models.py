from django.db import models
from apps.accounts.models import User


class AuditLog(models.Model):
    """
    Records all significant admin actions for accountability.
    Important for a government agency context like PESO.
    """
    ACTION_VERIFY = "verify"
    ACTION_REJECT = "reject"
    ACTION_DEACTIVATE = "deactivate"
    ACTION_REACTIVATE = "reactivate"
    ACTION_IMPORT = "import"
    ACTION_EDIT = "edit"
    ACTION_DELETE = "delete"
    ACTION_RESET_PASSWORD = "reset_password"

    ACTION_CHOICES = [
        (ACTION_VERIFY, "Verified Company"),
        (ACTION_REJECT, "Rejected Verification"),
        (ACTION_DEACTIVATE, "Deactivated Account"),
        (ACTION_REACTIVATE, "Reactivated Account"),
        (ACTION_IMPORT, "Imported Records"),
        (ACTION_EDIT, "Edited Record"),
        (ACTION_DELETE, "Deleted Record"),
        (ACTION_RESET_PASSWORD, "Reset Password"),
    ]

    admin = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="audit_logs"
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    target_model = models.CharField(max_length=100,
        help_text="The model that was acted on e.g. 'Company', 'JobseekerProfile'.")
    target_id = models.PositiveIntegerField(
        help_text="The primary key of the record that was acted on.")
    notes = models.TextField(blank=True,
        help_text="Optional notes e.g. reason for rejection or deactivation.")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_display()} by {self.admin} on {self.target_model} #{self.target_id}"


class ImportBatch(models.Model):
    """
    Tracks each bulk import of PESO's existing database records.
    Allows admins to review and roll back imports if needed.
    """
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETE = "complete"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETE, "Complete"),
        (STATUS_FAILED, "Failed"),
    ]

    IMPORT_JOBSEEKERS = "jobseekers"
    IMPORT_COMPANIES = "companies"

    IMPORT_TYPE_CHOICES = [
        (IMPORT_JOBSEEKERS, "Jobseekers"),
        (IMPORT_COMPANIES, "Companies"),
    ]

    imported_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="import_batches"
    )
    import_type = models.CharField(max_length=20, choices=IMPORT_TYPE_CHOICES)
    file = models.FileField(upload_to="imports/")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # Results
    total_rows = models.PositiveIntegerField(default=0)
    successful_imports = models.PositiveIntegerField(default=0)
    failed_imports = models.PositiveIntegerField(default=0)
    error_log = models.JSONField(default=list, blank=True,
        help_text="List of row-level errors encountered during import.")

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "import_batches"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_import_type_display()} import by {self.imported_by} on {self.created_at:%Y-%m-%d}"


class SiteSettings(models.Model):
    """
    Global settings the PESO admin can configure without touching code.
    Only one record should ever exist — enforced by the save() override.
    """
    compatibility_threshold = models.FloatField(default=80.0,
        help_text="Minimum compatibility score to trigger a 'New Compatible Job' notification.")
    hard_to_fill_days = models.PositiveIntegerField(default=30,
        help_text="Number of days a job must be open before being flagged as hard to fill.")
    hard_to_fill_applicant_threshold = models.PositiveIntegerField(default=3,
        help_text="Maximum applicant count for a job to be considered hard to fill.")
    max_hide_suggestions = models.PositiveIntegerField(default=5,
        help_text="Number of hidden jobs from the same company before suggesting a bulk hide.")
    maintenance_mode = models.BooleanField(default=False,
        help_text="Puts the site in maintenance mode — only admins can log in.")
    maintenance_message = models.TextField(blank=True,
        help_text="Message shown to users during maintenance mode.")

    # PESO Iloilo contact info (surfaced in footer + Help page).
    office_address = models.CharField(max_length=255, blank=True, default="",
        help_text="PESO Iloilo City office address (street, city, ZIP).")
    contact_email  = models.EmailField(blank=True, default="",
        help_text="Public-facing contact email shown in the footer.")
    hotline        = models.CharField(max_length=40, blank=True, default="",
        help_text="Public-facing hotline / landline number.")

    # Matching engine weights (must sum to 1.0). Defaults mirror the
    # historical constants in apps.matching.engine.
    weight_skills         = models.FloatField(default=0.40,
        help_text="Weight for skills match in the compatibility score (0.0-1.0).")
    weight_education      = models.FloatField(default=0.25,
        help_text="Weight for education match (0.0-1.0).")
    weight_experience     = models.FloatField(default=0.25,
        help_text="Weight for experience match (0.0-1.0).")
    weight_certifications = models.FloatField(default=0.10,
        help_text="Weight for certifications match (0.0-1.0).")

    updated_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="settings_updates"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "site_settings"
        verbose_name_plural = "Site Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "Site Settings"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class UserReport(models.Model):
    """A user-submitted report about another account (jobseeker or employer).

    Phase 1 captures the minimum data shown in the admin dashboard's
    User Reports table; a full review workflow lands in a later phase.
    """
    ACCOUNT_JOBSEEKER = "jobseeker"
    ACCOUNT_EMPLOYER  = "employer"
    ACCOUNT_TYPE_CHOICES = [
        (ACCOUNT_JOBSEEKER, "Jobseeker"),
        (ACCOUNT_EMPLOYER,  "Employer"),
    ]

    STATUS_OPEN     = "open"
    STATUS_REVIEWED = "reviewed"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = [
        (STATUS_OPEN,      "Open"),
        (STATUS_REVIEWED,  "Reviewed"),
        (STATUS_DISMISSED, "Dismissed"),
    ]

    # Who/what the report is about. Exactly one of these should be set.
    reported_jobseeker = models.ForeignKey(
        'jobseekers.JobseekerProfile', on_delete=models.CASCADE,
        null=True, blank=True, related_name='reports_received',
    )
    reported_company = models.ForeignKey(
        'employers.Company', on_delete=models.CASCADE,
        null=True, blank=True, related_name='reports_received',
    )
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    description  = models.TextField(help_text="Short description of the report (e.g. 'Profanity in application message').")
    filed_by     = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reports_filed',
    )
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    created_at   = models.DateTimeField(auto_now_add=True)
    reviewed_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "user_reports"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report against {self.account_label} — {self.get_status_display()}"

    @property
    def account_label(self):
        if self.reported_jobseeker:
            return f"{self.reported_jobseeker.first_name} {self.reported_jobseeker.last_name}"
        if self.reported_company:
            return self.reported_company.name
        return "Unknown"

    @property
    def filed_by_label(self):
        if not self.filed_by:
            return "(deleted user)"
        try:
            if self.filed_by.is_jobseeker:
                p = self.filed_by.jobseeker_profile
                return f"{p.first_name} {p.last_name}"
            if self.filed_by.is_employer:
                return self.filed_by.employer_profile.company.name
        except Exception:
            pass
        return self.filed_by.email


class AdminAnnouncement(models.Model):
    """A broadcast message from a PESO admin to jobseekers, employers, or both.
    Appears in the recipients' inboxes alongside applications and interview schedules.
    """
    AUDIENCE_ALL = "all"
    AUDIENCE_JOBSEEKERS = "jobseekers"
    AUDIENCE_EMPLOYERS = "employers"
    AUDIENCE_CHOICES = [
        (AUDIENCE_ALL, "All Users"),
        (AUDIENCE_JOBSEEKERS, "Jobseekers Only"),
        (AUDIENCE_EMPLOYERS, "Employers Only"),
    ]

    sender = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="announcements_sent"
    )
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default=AUDIENCE_ALL)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "admin_announcements"
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.subject} → {self.get_audience_display()} ({self.sent_at:%Y-%m-%d})"