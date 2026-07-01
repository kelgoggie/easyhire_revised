"""Seed the FAQ table with the questions previously hardcoded in
templates/help/_help_body.html. Runs once on migrate; reversible.

If any FAQ row already exists (e.g. re-running migrations after admin
edits), we skip seeding entirely to avoid overwriting live content.
"""
from django.db import migrations


JOBSEEKER = "jobseeker"
EMPLOYER  = "employer"


EMPLOYER_FAQS = [
    (
        "How do I post a new job?",
        "From your dashboard, click <strong>My Job Posts</strong> in the sidebar, then <strong>Create New Job</strong>. "
        "Fill in the title, description, location, requirements (skills, education, experience, certifications), "
        "and the number of slots. Save to publish.",
    ),
    (
        "How do I review applications?",
        "Open the job from <strong>My Job Posts</strong> and click <strong>View Applicants</strong>. Each applicant card has a "
        "<strong>View Application</strong> button that opens their message in a modal. From there you can <strong>Proceed</strong>, "
        "<strong>Reject</strong>, or just close out. Proceeding moves the application to <strong>In Progress</strong> — at that point "
        "you can message the candidate, send requirements, arrange interviews, and eventually use <strong>Mark as Hired</strong>.",
    ),
    (
        "What's the difference between In Progress and Hired?",
        "<strong>In Progress</strong> means you've decided to proceed with the applicant — they're being considered, you can "
        "message them and gather requirements, and you can still reject from this state. <strong>Hired</strong> is final: it adds "
        "the role to the jobseeker's work history, reduces the job's open slots by one, and adds the person to the Employees list "
        "on your company profile.",
    ),
    (
        "How do I close a job that's been filled?",
        "On <strong>My Job Posts</strong>, open the dot menu (top right of each card) and pick <strong>Close Job</strong>. "
        "Closed jobs stop receiving new applications and disappear from jobseeker recommendations, but stay on record so you "
        "can reopen them anytime from the same menu. EasyHire also auto-decrements your slot count each time you mark someone Hired.",
    ),
    (
        "Someone we hired has left — what do I do?",
        "Open the candidate's profile from your Employees list and click <strong>Un-hire</strong>. You can backdate the end "
        "date if needed. The hire stays on record (so you can still see who worked for you and when) and the corresponding job "
        "slot reopens automatically.",
    ),
    (
        "What do the match scores mean?",
        "Each applicant gets a score from 0-100 based on how closely their resume matches your job's requirements "
        "(skills, education, experience, certifications). Tiers range from <strong>Perfect Match</strong> (98+) down to "
        "<strong>Poor Match</strong>. Recommended Candidates surfaces people who haven't applied but match strongly — useful "
        "when you have a hard-to-fill role.",
    ),
    (
        "How do I update my company information?",
        "Click your company avatar on the navbar and choose <strong>Company Profile</strong>. To change your personal contact "
        "details, password, or to deactivate your account, go to <strong>Settings</strong> in the sidebar.",
    ),
    (
        "Why did PESO remove one of my job posts?",
        "PESO administrators may remove postings that violate platform policy (duplicate listings, misleading content, "
        "discriminatory language, etc.). You'll receive a notification with the specific reason. If you believe the removal "
        "was a mistake, contact PESO Iloilo City below.",
    ),
]


JOBSEEKER_FAQS = [
    (
        "How do I apply for a job?",
        "Open any job from the <strong>Jobs For You</strong> page or your search results and click <strong>Apply</strong>. "
        "You can optionally include a short application message — once submitted, your application can't be edited or withdrawn, "
        "so review it carefully before confirming.",
    ),
    (
        "What does the match score mean?",
        "Match scores reflect how well your resume aligns with a job's requirements. Tiers range from "
        "<strong>Perfect</strong> (98+) and <strong>Great</strong> (90+) down to <strong>Poor</strong>. "
        "The algorithm weighs your skills, education, experience, certifications, location, and sector profile. "
        "The more complete your resume, the more accurate the match.",
    ),
    (
        "How do I edit my resume?",
        "Go to <strong>Resume</strong> in the sidebar and click <strong>Edit Resume</strong>. You can add or remove education, "
        "skills, work experience, and certifications. If you have an existing PDF resume, use <strong>Upload PDF</strong> to "
        "autofill the form — you can still review and tweak the fields before saving.",
    ),
    (
        "How do I update my personal information?",
        "Go to <strong>Settings</strong> and click <strong>Edit Personal Information</strong>. You'll be asked to upload a "
        "valid Philippine ID for verification (PhilSys, Passport, Driver's License, UMID, and many others are accepted). "
        "Once submitted, PESO Administrators review your request within <strong>2 business days</strong>.",
    ),
    (
        "How do I see jobs I've liked or hidden?",
        "On the <strong>Jobs For You</strong> page, switch to the <strong>Liked</strong> or <strong>Hidden</strong> tab at "
        "the top. Hidden jobs won't appear in your main recommendations, but you can unhide them at any time by clicking "
        "the slashed-eye icon on the card.",
    ),
    (
        "Why am I not seeing personalised job recommendations?",
        "Recommendations require a complete resume. Visit the <strong>Resume</strong> page and fill in your skills, "
        "education, and work experience. Once your resume is marked complete, the matching engine starts producing "
        "personalised results.",
    ),
    (
        "What information do employers see about me?",
        "Employers see the resume fields you've filled in (skills, experience, education, certifications) along with the "
        "sector badges that apply to you. You can control visibility from the <strong>Privacy &amp; Preferences</strong> section "
        "of Settings — including whether your profile stays visible after you've been tagged as Hired, and which employers "
        "can see your sector badges.",
    ),
    (
        "How do I deactivate my account?",
        "Go to <strong>Settings → Deactivate Account</strong> and confirm with your password. Your profile will be hidden "
        "from employers and you won't be able to log in, but your data is preserved so you can return later. To reactivate, "
        "or to request permanent deletion, contact PESO Iloilo City directly.",
    ),
]


def seed(apps, schema_editor):
    FAQ = apps.get_model("admin_panel", "FAQ")
    if FAQ.objects.exists():
        return  # Already populated (or admin-edited) — don't clobber.
    rows = []
    for i, (q, a) in enumerate(JOBSEEKER_FAQS):
        rows.append(FAQ(question=q, answer=a, audience=JOBSEEKER, order=i))
    for i, (q, a) in enumerate(EMPLOYER_FAQS):
        rows.append(FAQ(question=q, answer=a, audience=EMPLOYER, order=i))
    FAQ.objects.bulk_create(rows)


def unseed(apps, schema_editor):
    FAQ = apps.get_model("admin_panel", "FAQ")
    FAQ.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("admin_panel", "0007_faq"),
    ]

    operations = [
        migrations.RunPython(seed, reverse_code=unseed),
    ]
