"""Outbound transactional emails for high-impact events.

Failures are swallowed (logged to console) so a flaky SMTP can never crash a
status-update request. In-app bell notifications are the source of truth; email
is a convenience.
"""
from django.core.mail import EmailMessage
from django.conf import settings


# Seeded/demo accounts use these reserved-suffix domains — they never resolve
# in DNS, so Gmail SMTP hangs 5–30s doing MX lookups before giving up. That
# blocks the user-facing request and can push it past Render's proxy timeout,
# surfacing as a 502/500 to the browser even though `_send` catches the SMTP
# exception. Skipping SMTP entirely for these domains keeps demos snappy and
# the in-app inbox path still records the message.
_SKIP_SMTP_SUFFIXES = ('@easyhire.test', '@easyhire.extra', '@easyhire.local')


def _send(to_email, subject, body):
    if not to_email:
        return False
    low = to_email.strip().lower()
    if any(low.endswith(s) for s in _SKIP_SMTP_SUFFIXES):
        print(f'[email] skipping SMTP for demo/test recipient: {to_email}')
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
        subject = f'{company} is moving forward with your application for {job_title}'
        body = (
            f"Hi {first_name},\n\n"
            f"Good news — {company} has decided to proceed with your application for {job_title}.\n"
            f"Your application status is now In Progress. They may be in touch about "
            f"requirements, an interview, or a hire offer.\n\n"
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


def email_employer_contact(contact):
    """Deliver an employer's outbound message (requirements or interview schedule)
    to the jobseeker's contact email. Returns True on send, False otherwise.
    """
    if not contact or not contact.recipient:
        return False
    js = contact.recipient
    to_email = js.contact_email or (js.user.email if js.user else '')
    if not to_email:
        return False

    sender_name = ''
    if contact.sender:
        prof = getattr(contact.sender, 'employer_profile', None)
        if prof:
            sender_name = f"{prof.first_name} {prof.last_name}".strip()
    if not sender_name:
        sender_name = contact.company.name if contact.company else 'An employer'

    company = contact.company.name if contact.company else ''
    job_line = f" regarding {contact.job.title}" if contact.job else ''

    header = (
        f"Hi {js.first_name},\n\n"
        f"{sender_name} from {company} has reached out to you{job_line} through EasyHire.\n"
        f"-----\n\n"
    )
    footer = (
        f"\n\n-----\n"
        f"This message was sent via EasyHire. You can reply directly to this email "
        f"to respond to {sender_name}.\n"
        f"— EasyHire"
    )
    body = header + (contact.body or '') + footer
    ok = _send(to_email, contact.subject or '(no subject)', body)
    # Snapshot what we actually delivered to.
    if ok:
        contact.delivered_to_email = to_email
        contact.save(update_fields=['delivered_to_email'])
    return ok


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
