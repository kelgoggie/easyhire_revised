from django.db import models


class CompatibilityScore(models.Model):
    jobseeker = models.ForeignKey(
        "jobseekers.JobseekerProfile", on_delete=models.CASCADE, related_name="compatibility_scores"
    )
    job = models.ForeignKey(
        "jobs.JobPosting", on_delete=models.CASCADE, related_name="compatibility_scores"
    )
    score = models.FloatField(help_text="Overall compatibility 0–100.")
    breakdown = models.JSONField(default=dict,
        help_text="Stores per-category scores and matched/missing details.")
    computed_at = models.DateTimeField(auto_now=True)
    is_stale = models.BooleanField(default=False,
        help_text="Set True when resume or job requirements change to trigger recompute.")

    class Meta:
        db_table = "compatibility_scores"
        unique_together = ("jobseeker", "job")

    def __str__(self):
        return f"{self.jobseeker} ↔ {self.job.title}: {self.score:.1f}%"


class JobMatchingWeights(models.Model):
    """Per-job override of the standard matching criteria weights.

    A job without a row here (or with use_custom_weights=False) falls back
    to PESO's site-wide defaults in apps.admin_panel.models.SiteSettings —
    see apps.matching.engine.get_weights(). Weights here don't need to sum
    to 1.0 in storage; the engine normalizes whatever's active for a given
    job (these four plus any JobCustomCriterion rows) at compute time, so
    a partial edit never produces a broken score.
    """
    job = models.OneToOneField(
        "jobs.JobPosting", on_delete=models.CASCADE, related_name="matching_weights"
    )
    use_custom_weights = models.BooleanField(default=False,
        help_text="If off, this job uses PESO's site-wide default weights and ignores the fields below.")

    weight_skills = models.FloatField(default=0.40,
        help_text="Weight for skills match (0.0-1.0).")
    weight_education = models.FloatField(default=0.25,
        help_text="Weight for education match (0.0-1.0).")
    weight_experience = models.FloatField(default=0.25,
        help_text="Weight for experience match (0.0-1.0).")
    weight_certifications = models.FloatField(default=0.10,
        help_text="Weight for certifications match (0.0-1.0).")

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "job_matching_weights"
        verbose_name_plural = "Job Matching Weights"

    def __str__(self):
        return f"Matching weights for {self.job.title}"


class Match(models.Model):
    jobseeker = models.ForeignKey(
        "jobseekers.JobseekerProfile", on_delete=models.CASCADE, related_name="matches"
    )
    company = models.ForeignKey(
        "employers.Company", on_delete=models.CASCADE, related_name="matches"
    )
    job = models.ForeignKey(
        "jobs.JobPosting", on_delete=models.CASCADE, related_name="matches"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    conversation = models.OneToOneField(
        "messaging.Conversation", null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        db_table = "matches"
        unique_together = ("jobseeker", "company", "job")

    def __str__(self):
        return f"Match: {self.jobseeker} ↔ {self.company.name} for {self.job.title}"