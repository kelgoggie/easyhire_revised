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