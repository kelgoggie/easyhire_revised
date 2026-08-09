from django.db import models

from django.db import models
from apps.accounts.models import User


class Notification(models.Model):
    COMPANY_LIKED_YOU = 'company_liked_you'
    JOBSEEKERS_LIKED_JOB = 'jobseekers_liked_job'
    MATCH = 'match'
    JOB_DELETED_BY_ADMIN = 'job_deleted_by_admin'
    PERSONAL_INFO_APPROVED = 'personal_info_approved'
    PERSONAL_INFO_REJECTED = 'personal_info_rejected'
    # PESO reviewed the jobseeker's uploaded ID document.
    ID_VERIFICATION_APPROVED = 'id_verification_approved'   # jobseeker-facing
    ID_VERIFICATION_DENIED   = 'id_verification_denied'     # jobseeker-facing
    NEW_APPLICATION       = 'new_application'        # employer-facing: new job application received
    APPLICATION_ACCEPTED  = 'application_accepted'   # jobseeker-facing
    APPLICATION_REJECTED  = 'application_rejected'   # jobseeker-facing
    APPLICATION_HIRED     = 'application_hired'      # jobseeker-facing
    EMPLOYER_CONTACTED    = 'employer_contacted'     # jobseeker-facing: employer sent requirements or interview
    # "Invite to Apply" — a lightweight nudge (no inbox row, no email, just
    # a notification with a View Job link). Employer clicks the button on
    # the Recommended Jobseekers card; jobseeker gets a bell notification.
    INVITED_TO_APPLY      = 'invited_to_apply'       # jobseeker-facing
    # Two-step hire flow: employer offers, jobseeker accepts/declines.
    HIRE_OFFERED          = 'hire_offered'           # jobseeker-facing: employer wants to mark them as Hired
    HIRE_ACCEPTED         = 'hire_accepted'          # employer-facing: jobseeker confirmed
    HIRE_DECLINED         = 'hire_declined'          # employer-facing: jobseeker said no
    # Employer clicked Un-hire on a previously-hired jobseeker. Fires a
    # jobseeker-facing notification so they see their employment status
    # change without having to check /applications/.
    APPLICATION_UNHIRED   = 'application_unhired'    # jobseeker-facing
    # PESO admin published a broadcast announcement. Fanned out to every
    # user in the target audience so each recipient gets a bell + toast,
    # not just an inbox row.
    NEW_ANNOUNCEMENT      = 'new_announcement'

    TYPE_CHOICES = [
        (COMPANY_LIKED_YOU,      'Company Liked You'),
        (JOBSEEKERS_LIKED_JOB,   'Jobseekers Liked Job'),
        (MATCH,                  'Match'),
        (JOB_DELETED_BY_ADMIN,   'Job Deleted by Admin'),
        (PERSONAL_INFO_APPROVED, 'Personal Info Change Approved'),
        (PERSONAL_INFO_REJECTED, 'Personal Info Change Rejected'),
        (ID_VERIFICATION_APPROVED, 'ID Verification Approved'),
        (ID_VERIFICATION_DENIED,   'ID Verification Denied'),
        (NEW_APPLICATION,        'New Job Application'),
        (APPLICATION_ACCEPTED,   'Application Accepted'),
        (APPLICATION_REJECTED,   'Application Rejected'),
        (APPLICATION_HIRED,      'Application Hired'),
        (EMPLOYER_CONTACTED,     'Employer Sent Contact'),
        (INVITED_TO_APPLY,       'Invited to Apply'),
        (HIRE_OFFERED,           'Hire Offered'),
        (HIRE_ACCEPTED,          'Hire Accepted'),
        (HIRE_DECLINED,          'Hire Declined'),
        (APPLICATION_UNHIRED,    'Application Un-hired'),
        (NEW_ANNOUNCEMENT,       'New PESO Announcement'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_notifications')
    notif_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    company = models.ForeignKey('employers.Company', on_delete=models.CASCADE, null=True, blank=True)
    jobseeker = models.ForeignKey('jobseekers.JobseekerProfile', on_delete=models.CASCADE, null=True, blank=True)
    # Job FK is SET_NULL: when an admin deletes a job, the notification about that
    # deletion should survive (with the job title snapshotted in liker_preview).
    job = models.ForeignKey('jobs.JobPosting', on_delete=models.SET_NULL, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # For grouped employer notifications — stores count of likers,
    # OR (for JOB_DELETED_BY_ADMIN) a snapshot of the deleted job's title.
    liker_count = models.PositiveIntegerField(default=1)
    liker_preview = models.CharField(max_length=200, blank=True,
        help_text="e.g. 'Juan, Maria and 9+ others', or a deleted job's title snapshot.")
    # Free-form admin-supplied message (currently used for job-deletion reasons).
    admin_message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'activity_notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notif_type_display()} → {self.recipient.email}"