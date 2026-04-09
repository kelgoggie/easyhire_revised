from django.db import models
from apps.accounts.models import User


class Conversation(models.Model):
    jobseeker = models.ForeignKey(
        "jobseekers.JobseekerProfile", on_delete=models.CASCADE,
        related_name="conversations",
        default=1
    )
    company = models.ForeignKey(
        "employers.Company", on_delete=models.CASCADE,
        related_name="conversations",
        default=1
    )
    job = models.ForeignKey(
        "jobs.JobPosting", on_delete=models.CASCADE,
        related_name="conversations", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversations"
        unique_together = ("jobseeker", "company", "job")

    def __str__(self):
        return f"{self.jobseeker} ↔ {self.company.name}"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sent_messages"
    )
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "messages"
        ordering = ["sent_at"]

    def __str__(self):
        return f"Message from {self.sender.email} at {self.sent_at:%Y-%m-%d %H:%M}"


class Notification(models.Model):
    MATCH = "match"
    NEW_JOB_FOLLOWED = "new_job_followed"
    NEW_JOB_COMPATIBLE = "new_job_compatible"
    VERIFICATION_APPROVED = "verification_approved"
    VERIFICATION_DENIED = "verification_denied"
    NEW_MESSAGE = "new_message"
    HIDE_SUGGESTION = "hide_suggestion"

    NOTIFICATION_TYPES = [
        (MATCH, "New Match"),
        (NEW_JOB_FOLLOWED, "New Job from Followed Company"),
        (NEW_JOB_COMPATIBLE, "New Compatible Job (80%+)"),
        (VERIFICATION_APPROVED, "Verification Approved"),
        (VERIFICATION_DENIED, "Verification Denied"),
        (NEW_MESSAGE, "New Message"),
        (HIDE_SUGGESTION, "Hide Suggestion"),
    ]

    recipient = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    link = models.CharField(max_length=300, blank=True,
        help_text="URL to redirect the user when they click the notification.")

    # Optional references so we can link directly to the relevant object
    job = models.ForeignKey(
        "jobs.JobPosting", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="notifications"
    )
    match = models.ForeignKey(
        "matching.Match", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="notifications"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_notification_type_display()} → {self.recipient.email}"