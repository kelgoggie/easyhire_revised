"""One-off booster for defense demo: adds 7 jobseekers with widowed /
separated / annulled civil statuses (the underrepresented buckets on the
demographics pie), and 20 more jobs across existing companies with a
wider variety of titles.

Idempotent — gated on `@easyhire.boost` marker users. Re-runs are no-ops
unless --force is passed.

Timestamps are backdated across the last 180 days, same pattern as
seed_more.

Run:
    python manage.py seed_boost
"""
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.employers.models import Company
from apps.jobseekers.models import (
    JobseekerProfile, Education, Skill, Certification, WorkExperience,
)
from apps.jobs.models import (
    JobPosting, JobEducationRequirement, JobSkillRequirement,
    JobCertificationRequirement, JobExperienceRequirement,
)


PASSWORD = 'easyhire2001'
BOOST_DOMAIN = 'easyhire.boost'


def _mark_email_verified(user, email):
    try:
        from allauth.account.models import EmailAddress
    except ImportError:
        return
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={'verified': True, 'primary': True},
    )


def _backdate(model, pk, field, when):
    model.objects.filter(pk=pk).update(**{field: when})


def _random_past(days_min=1, days_max=180):
    now = timezone.now()
    return now - timedelta(
        days=random.randint(days_min, days_max),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )


# 7 jobseekers, each with a specific civil status from the underrepresented
# buckets. Mix of ages, sexes, barangays so the demographic pies also gain
# some variety in the neighbors.
BOOST_JOBSEEKERS = [
    {'first': 'Corazon',  'last': 'Aquino',    'sex': 'F', 'age': 52, 'barangay': 'Jaro',              'civil': 'widowed'},
    {'first': 'Feliciano','last': 'Bacsal',    'sex': 'M', 'age': 47, 'barangay': 'La Paz',            'civil': 'widowed'},
    {'first': 'Purita',   'last': 'Concepcion','sex': 'F', 'age': 39, 'barangay': 'Molo',              'civil': 'separated'},
    {'first': 'Rodolfo',  'last': 'Damasco',   'sex': 'M', 'age': 43, 'barangay': 'Mandurriao',        'civil': 'separated'},
    {'first': 'Ines',     'last': 'Encarnacion','sex': 'F', 'age': 36, 'barangay': 'Arevalo Proper',   'civil': 'annulled'},
    {'first': 'Marcelo',  'last': 'Fajardo',   'sex': 'M', 'age': 41, 'barangay': 'Lapuz Norte',       'civil': 'annulled'},
    {'first': 'Estrella', 'last': 'Gerona',    'sex': 'F', 'age': 45, 'barangay': 'City Proper',       'civil': 'widowed'},
]


# 20 new job templates. Broader variety than seed_more — light service,
# health, construction, admin, tech, hospitality. Kept short so each fits
# nicely on a card.
BOOST_JOB_TEMPLATES = [
    {'title': 'Barista',                         'edu': 'senior_high', 'edu_course': '',                         'exp_months': 0,  'skills': ['Customer Service', 'Cash Handling', 'Food Safety'],       'certs': [], 'slots': 4, 'desc': 'Prepare and serve espresso drinks, maintain the coffee bar, and greet guests. Rotating shifts, on-site.'},
    {'title': 'Housekeeping Attendant',          'edu': 'junior_high', 'edu_course': '',                         'exp_months': 0,  'skills': ['Physical Stamina', 'Attention to Detail'],                'certs': [], 'slots': 6, 'desc': 'Clean and maintain guest rooms and public areas of the hotel. Full-time, split shift.'},
    {'title': 'Delivery Rider',                  'edu': 'junior_high', 'edu_course': '',                         'exp_months': 6,  'skills': ['Motorcycle Riding', 'Customer Service', 'Navigation'],    'certs': [('Non-Professional Driver\'s License', 'LTO')], 'slots': 8, 'desc': 'Deliver food, parcels, and documents across Iloilo City. Must own a serviceable motorcycle.'},
    {'title': 'Security Guard',                  'edu': 'senior_high', 'edu_course': '',                         'exp_months': 12, 'skills': ['Physical Stamina', 'Communication', 'Attention to Detail'], 'certs': [('Security Guard License', 'PNP SOSIA')], 'slots': 5, 'desc': 'Post at the main entrance, monitor CCTV, and log visitors. 12-hour shifts, full uniform provided.'},
    {'title': 'Baker',                           'edu': 'senior_high', 'edu_course': '',                         'exp_months': 6,  'skills': ['Baking', 'Food Safety', 'Time Management'],               'certs': [], 'slots': 3, 'desc': 'Bake bread, pastries, and cakes for the morning service. Early-start schedule (4am).'},
    {'title': 'Massage Therapist',               'edu': 'vocational',  'edu_course': 'TESDA Massage NC II',       'exp_months': 6,  'skills': ['Swedish Massage', 'Deep Tissue', 'Customer Service'],     'certs': [('TESDA NC II Massage', 'TESDA')], 'slots': 3, 'desc': 'Provide therapeutic massage to hotel guests and spa clients. Trained on hotel-brand protocol.'},
    {'title': 'Junior Bookkeeper',               'edu': 'bachelor',    'edu_course': 'Accountancy',              'exp_months': 6,  'skills': ['Bookkeeping', 'Microsoft Excel', 'QuickBooks'],           'certs': [], 'slots': 2, 'desc': 'Support senior accountants with data entry, bank reconciliation, and monthly reports.'},
    {'title': 'Warehouse Supervisor',            'edu': 'senior_high', 'edu_course': '',                         'exp_months': 24, 'skills': ['Inventory Management', 'Leadership', 'Forklift Operation'], 'certs': [], 'slots': 1, 'desc': 'Oversee 8-person warehouse team, manage inventory counts, and coordinate incoming shipments.'},
    {'title': 'Front Office Receptionist',       'edu': 'senior_high', 'edu_course': '',                         'exp_months': 6,  'skills': ['Customer Service', 'Microsoft Office', 'Communication'],   'certs': [], 'slots': 2, 'desc': 'Greet walk-ins, answer phones, and handle basic administrative tasks at reception.'},
    {'title': 'Digital Marketing Associate',     'edu': 'bachelor',    'edu_course': 'Marketing',                'exp_months': 6,  'skills': ['Social Media Marketing', 'Canva', 'Copywriting'],        'certs': [], 'slots': 2, 'desc': 'Manage social media accounts, draft post copy, and monitor campaign performance.'},
    {'title': 'Graphic Designer',                'edu': 'bachelor',    'edu_course': 'Multimedia Arts',          'exp_months': 12, 'skills': ['Photoshop', 'Illustrator', 'Canva'],                     'certs': [], 'slots': 2, 'desc': 'Design marketing materials, social media graphics, and print collateral for campaigns.'},
    {'title': 'Video Editor',                    'edu': 'bachelor',    'edu_course': 'Multimedia Arts',          'exp_months': 12, 'skills': ['Premiere Pro', 'DaVinci Resolve', 'Storytelling'],       'certs': [], 'slots': 1, 'desc': 'Edit short-form video for social media and campaign content. Motion graphics is a plus.'},
    {'title': 'Medical Technologist',            'edu': 'bachelor',    'edu_course': 'Medical Technology',       'exp_months': 12, 'skills': ['Lab Analysis', 'Blood Chemistry', 'Attention to Detail'], 'certs': [('PRC Medtech License', 'Professional Regulation Commission')], 'slots': 2, 'desc': 'Run diagnostic lab tests on patient samples. Board-passed medtech required.'},
    {'title': 'Physical Therapist',              'edu': 'bachelor',    'edu_course': 'Physical Therapy',         'exp_months': 6,  'skills': ['Rehabilitation', 'Patient Care', 'Manual Therapy'],       'certs': [('PRC PT License', 'Professional Regulation Commission')], 'slots': 1, 'desc': 'Provide rehabilitation therapy for orthopedic and neurological patients.'},
    {'title': 'Electrical Engineer',             'edu': 'bachelor',    'edu_course': 'Electrical Engineering',   'exp_months': 24, 'skills': ['AutoCAD', 'Electrical Design', 'Project Management'],    'certs': [('PRC EE License', 'Professional Regulation Commission')], 'slots': 1, 'desc': 'Design and supervise electrical systems for commercial buildings.'},
    {'title': 'Civil Engineer',                  'edu': 'bachelor',    'edu_course': 'Civil Engineering',        'exp_months': 24, 'skills': ['AutoCAD', 'Site Supervision', 'Project Management'],    'certs': [('PRC CE License', 'Professional Regulation Commission')], 'slots': 1, 'desc': 'Oversee residential and light commercial construction projects. Site-based role.'},
    {'title': 'Elementary Teacher',              'edu': 'bachelor',    'edu_course': 'Elementary Education',     'exp_months': 6,  'skills': ['Lesson Planning', 'Classroom Management', 'Communication'], 'certs': [('LET License', 'Professional Regulation Commission')], 'slots': 4, 'desc': 'Teach Grade 1–6 across core subjects. LET-passed required.'},
    {'title': 'Preschool Teacher',               'edu': 'bachelor',    'edu_course': 'Early Childhood Education','exp_months': 0,  'skills': ['Child Development', 'Lesson Planning', 'Patience'],       'certs': [], 'slots': 3, 'desc': 'Teach and care for children ages 3–5 in a structured preschool setting.'},
    {'title': 'HR Assistant',                    'edu': 'bachelor',    'edu_course': 'Human Resources',          'exp_months': 6,  'skills': ['Recruitment', 'Microsoft Office', 'Communication'],       'certs': [], 'slots': 2, 'desc': 'Support recruitment, onboarding, and employee records. Entry-level HR role.'},
    {'title': 'Junior Data Analyst',             'edu': 'bachelor',    'edu_course': 'Statistics',               'exp_months': 6,  'skills': ['SQL', 'Microsoft Excel', 'Power BI'],                    'certs': [], 'slots': 2, 'desc': 'Pull reports, build dashboards, and support business intelligence work.'},
]


EDU_TEMPLATES_BY_LEVEL = {
    'bachelor':    ('BS Business Administration', 'University of the Philippines Visayas'),
    'vocational':  ('TESDA Vocational Training',  'Iloilo TESDA Training Center'),
    'senior_high': ('TVL Track',                  'Iloilo National High School'),
    'junior_high': ('Junior High School',         'Iloilo City National High School'),
}


class Command(BaseCommand):
    help = ('Add 7 widowed/separated/annulled jobseekers + 20 varied job '
            'postings across existing companies. Backdated up to 180 days.')

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
            help='Run even if boost seed marker (@easyhire.boost users) exists.')

    def handle(self, *args, **opts):
        random.seed(11)  # deterministic across runs

        marker = User.objects.filter(email__endswith=f'@{BOOST_DOMAIN}').exists()
        if marker and not opts['force']:
            self.stdout.write(self.style.WARNING(
                f'Boost seed already applied (@{BOOST_DOMAIN} users exist). '
                f'Re-run with --force to attempt again.'
            ))
            return

        # ── 7 boost jobseekers ────────────────────────────────────────
        today = date.today()
        seekers_created = 0
        for jd in BOOST_JOBSEEKERS:
            email = f"{jd['first'].lower()}.{jd['last'].lower()}@{BOOST_DOMAIN}"
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    'user_type': User.JOBSEEKER,
                    'is_active': True,
                    'consented_to_terms': True,
                    'consented_at': timezone.now(),
                },
            )
            user.set_password(PASSWORD)
            user.user_type = User.JOBSEEKER
            user.save()
            _mark_email_verified(user, email)

            signed_up = _random_past(days_min=10, days_max=170)
            _backdate(User, user.pk, 'created_at', signed_up)

            dob = date(today.year - jd['age'], random.randint(1, 12), random.randint(1, 28))
            profile, p_created = JobseekerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'first_name': jd['first'],
                    'last_name': jd['last'],
                    'sex': jd['sex'],
                    'date_of_birth': dob,
                    'civil_status': jd['civil'],
                    'street_barangay': f"{random.randint(10, 999)} {random.choice(['Iznart', 'Rizal', 'Luna', 'Bonifacio', 'Quezon'])} Street",
                    'barangay': jd['barangay'],
                    'city_municipality': 'Iloilo City',
                    'province': 'Iloilo',
                    'province_code': '063000000',
                    'phone': f"0917{random.randint(1000000, 9999999)}",
                    'contact_email': email,
                    'profile_complete': True,
                    'profile_visibility': 'public',
                    'sector_badge_visibility': 'public',
                    'bio': (
                        f"Experienced {jd['age']}-year-old jobseeker looking for "
                        f"stable work in Iloilo City. Reliable and diligent."
                    ),
                },
            )
            _backdate(JobseekerProfile, profile.pk, 'created_at', signed_up)

            if p_created:
                level = random.choice(['bachelor', 'vocational', 'senior_high'])
                course, inst = EDU_TEMPLATES_BY_LEVEL[level]
                Education.objects.create(
                    profile=profile, level=level, course_degree=course, institution=inst,
                    year_started=today.year - jd['age'] + 18,
                    year_ended=today.year - jd['age'] + 22,
                )
                for s in random.sample(
                    ['Customer Service', 'Microsoft Office', 'Communication',
                     'Time Management', 'Bookkeeping', 'Attention to Detail',
                     'Filing', 'Cash Handling', 'Physical Stamina'],
                    k=random.randint(3, 5),
                ):
                    Skill.objects.create(profile=profile, name=s)
                # Older jobseekers → 1–3 work experience rows
                for _ in range(random.randint(1, 3)):
                    yr_start = today.year - random.randint(3, jd['age'] - 20)
                    WorkExperience.objects.create(
                        profile=profile,
                        position=random.choice([
                            'Administrative Assistant', 'Sales Associate',
                            'Bookkeeper', 'Teacher', 'Nurse', 'Cashier',
                            'Customer Service Representative',
                        ]),
                        company=random.choice([
                            'SM City Iloilo', 'Robinsons Place Iloilo',
                            'Iloilo Provincial Capitol', 'St. Paul\'s Hospital',
                            'Iloilo Central Elementary School',
                        ]),
                        month_started='January', year_started=yr_start,
                        month_ended='December', year_ended=yr_start + random.randint(2, 5),
                        description='Prior professional experience.',
                    )

            seekers_created += 1
        self.stdout.write(self.style.SUCCESS(
            f'Boost jobseekers created / updated: {seekers_created} '
            f'(widowed / separated / annulled distribution)'
        ))

        # ── 20 additional jobs across existing companies ─────────────
        # Spread across whatever companies exist. Prefers the seed_demo
        # companies since they're the most "real"-looking, then falls
        # back to the seed_more extras.
        companies = list(Company.objects.all())
        if not companies:
            self.stdout.write(self.style.ERROR(
                'No companies exist yet — run seed_demo (and/or seed_more) first.'
            ))
            return

        jobs_created = 0
        for jt in BOOST_JOB_TEMPLATES:
            company = random.choice(companies)
            job, created = JobPosting.objects.get_or_create(
                company=company, title=jt['title'],
                defaults={
                    'description': jt['desc'],
                    'location_type': JobPosting.ILOILO,
                    'barangay_name': (company.main_branch_address or '').split(',')[0].strip() or 'Iloilo City',
                    'city': 'Iloilo City',
                    'slots': jt['slots'],
                    'status': JobPosting.STATUS_OPEN,
                    'contact_email': company.recruitment_email or company.company_email or '',
                },
            )
            if created:
                posted_at = _random_past(days_min=1, days_max=170)
                _backdate(JobPosting, job.pk, 'created_at', posted_at)

                JobEducationRequirement.objects.create(
                    job=job, level=jt['edu'], course_degree=jt['edu_course'],
                )
                JobExperienceRequirement.objects.create(
                    job=job, months_required=jt['exp_months'],
                    any_experience_accepted=True,
                )
                for s in jt['skills']:
                    JobSkillRequirement.objects.create(job=job, name=s, is_required=True)
                for cname, corg in jt['certs']:
                    JobCertificationRequirement.objects.create(
                        job=job, name=cname, issuing_org=corg, is_required=True,
                    )
                jobs_created += 1
        self.stdout.write(self.style.SUCCESS(
            f'Boost jobs created: {jobs_created} '
            f'(across {len(set(j.company_id for j in JobPosting.objects.all()))} companies)'
        ))

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Password for boost jobseekers: {PASSWORD}'
        ))
