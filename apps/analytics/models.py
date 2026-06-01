from django.db import models


class DailySnapshot(models.Model):
    """
    Stores a daily summary of platform statistics.
    A scheduled task (Celery beat) runs every night and creates one record per day.
    This allows PESO to view trends over time without expensive real-time queries.
    """
    date = models.DateField(unique=True)

    # User counts
    total_jobseekers = models.PositiveIntegerField(default=0)
    total_employers = models.PositiveIntegerField(default=0)
    new_jobseekers = models.PositiveIntegerField(default=0,
        help_text="New jobseekers registered on this date.")
    new_employers = models.PositiveIntegerField(default=0,
        help_text="New employers registered on this date.")

    # Job market
    total_job_postings = models.PositiveIntegerField(default=0)
    active_job_postings = models.PositiveIntegerField(default=0)
    new_job_postings = models.PositiveIntegerField(default=0)
    hard_to_fill_jobs = models.PositiveIntegerField(default=0)
    jobs_placed = models.PositiveIntegerField(default=0,
        help_text="Total mutual matches recorded up to this date.")
    new_matches = models.PositiveIntegerField(default=0,
        help_text="New matches created on this date.")

    # Matching performance
    avg_compatibility_score = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "daily_snapshots"
        ordering = ["-date"]

    def __str__(self):
        return f"Snapshot {self.date}"


class SectorSnapshot(models.Model):
    """
    Daily breakdown of jobseeker counts per sector.
    Separate from DailySnapshot to keep things clean and queryable.
    """
    snapshot = models.ForeignKey(
        DailySnapshot, on_delete=models.CASCADE, related_name="sector_breakdown"
    )
    sector_code = models.CharField(max_length=50)
    sector_label = models.CharField(max_length=100)
    jobseeker_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "sector_snapshots"
        unique_together = ("snapshot", "sector_code")

    def __str__(self):
        return f"{self.sector_label}: {self.jobseeker_count} on {self.snapshot.date}"


class EducationSnapshot(models.Model):
    """Daily breakdown of jobseeker counts per education level."""
    snapshot = models.ForeignKey(
        DailySnapshot, on_delete=models.CASCADE, related_name="education_breakdown"
    )
    level = models.CharField(max_length=50)
    level_label = models.CharField(max_length=100)
    jobseeker_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "education_snapshots"
        unique_together = ("snapshot", "level")

    def __str__(self):
        return f"{self.level_label}: {self.jobseeker_count} on {self.snapshot.date}"


class CompanyTypeSnapshot(models.Model):
    """Daily breakdown of company counts per type (Local, Overseas, BPO)."""
    snapshot = models.ForeignKey(
        DailySnapshot, on_delete=models.CASCADE, related_name="company_type_breakdown"
    )
    company_type = models.CharField(max_length=50)
    company_type_label = models.CharField(max_length=100)
    company_count = models.PositiveIntegerField(default=0)
    active_job_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "company_type_snapshots"
        unique_together = ("snapshot", "company_type")


class InDemandSkill(models.Model):
    """
    Weekly snapshot of the most in-demand skills based on job requirements.
    Useful for PESO to identify skills gaps and plan training programs.
    """
    week_start = models.DateField()
    skill_name = models.CharField(max_length=200)
    job_count = models.PositiveIntegerField(default=0,
        help_text="Number of active job postings requiring this skill.")
    avg_compatibility = models.FloatField(null=True, blank=True,
        help_text="Average compatibility score of jobseekers for jobs requiring this skill.")

    class Meta:
        db_table = "in_demand_skills"
        ordering = ["-week_start", "-job_count"]
        unique_together = ("week_start", "skill_name")

    def __str__(self):
        return f"{self.skill_name} — {self.job_count} jobs (week of {self.week_start})"


class LocationSnapshot(models.Model):
    """
    Weekly breakdown of jobseeker and job counts by barangay.
    Helps PESO identify underserved areas of Iloilo City.
    """
    week_start = models.DateField()
    barangay = models.CharField(max_length=200)
    jobseeker_count = models.PositiveIntegerField(default=0)
    job_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "location_snapshots"
        ordering = ["-week_start"]
        unique_together = ("week_start", "barangay")

    def __str__(self):
        return f"{self.barangay} — {self.jobseeker_count} jobseekers, {self.job_count} jobs (week of {self.week_start})"