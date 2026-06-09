"""Outbound transactional emails for high-impact events.

Failures are swallowed (logged to console) so a flaky SMTP can never crash a
status-update request. In-app bell notifications are the source of truth; email
is a convenience.
"""
from django.core.mail import EmailMessage
from django.conf import settings


def _send(to_email, subject, body):
    if not to_email:
        return False
    try:
        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        msg.send(fail_silently=False)
        return True
    except Exception as exc:
        # Don't let SMTP failures break the user-facing request.
        print(f'[email] failed to send to {to_email}: {exc}')
        return False


def email_application_status_change(application, action):
    """Email the jobseeker on accept / reject / hire.

    `action` is one of 'accept', 'reject', 'hire'.
    """
    if not application or not application.jobseeker:
        return
    user = application.jobseeker.user
    if not user or not user.email:
        return

    first_name = application.jobseeker.first_name
    company    = application.job.company.name if application.job else 'A company'
    job_title  = application.job.title if application.job else 'the position'

    if action == 'accept':
        subject = f'{company} accepted your application for {job_title}'
        body = (
            f"Hi {first_name},\n\n"
            f"Good news — {company} has accepted your application for {job_title}!\n"
            f"They may be in touch with next steps soon.\n\n"
            f"View this on EasyHire: https://easyhire.ph/applications/\n\n"
            f"— EasyHire"
        )
    elif action == 'reject':
        subject = f'Update on your application to {company}'
        body = (
            f"Hi {first_name},\n\n"
            f"Thank you for applying to {job_title} at {company}. After review, "
            f"the employer has decided not to move forward with your application this time.\n\n"
            f"Don't be discouraged — keep an eye on Jobs For You for fresh matches.\n\n"
            f"— EasyHire"
        )
    elif action == 'hire':
        subject = f'Congratulations — you were hired by {company}!'
        body = (
            f"Hi {first_name},\n\n"
            f"Huge congrats! {company} has officially hired you for {job_title}.\n"
            f"This role has been added to your work history on EasyHire.\n\n"
            f"View this on EasyHire: https://easyhire.ph/applications/\n\n"
            f"— EasyHire"
        )
    else:
        return

    _send(user.email, subject, body)


def email_personal_info_decision(change_request, approved):
    """Email the jobseeker when the admin approves or rejects their info change."""
    if not change_request:
        return
    user = change_request.profile.user
    if not user or not user.email:
        return

    first_name = change_request.profile.first_name
    if approved:
        subject = 'Your personal information change has been approved'
        body = (
            f"Hi {first_name},\n\n"
            f"PESO Iloilo City has reviewed and approved your personal information "
            f"change request. The updated details are now reflected on your profile.\n\n"
            f"View this on EasyHire: https://easyhire.ph/settings/\n\n"
            f"— EasyHire"
        )
    else:
        subject = 'Update on your personal information change request'
        body = (
            f"Hi {first_name},\n\n"
            f"PESO Iloilo City has reviewed your personal information change request "
            f"and decided not to approve it at this time. Your profile information is unchanged.\n"
            f"You can submit a new request from your Settings page.\n\n"
            f"— EasyHire"
        )
    _send(user.email, subject, body)
