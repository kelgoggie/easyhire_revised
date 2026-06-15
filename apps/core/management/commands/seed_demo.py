"""Seed local database with realistic demo data.

Creates 10 companies (each with one verified employer rep + 1-2 job posts) and
20 jobseekers with filled-in resumes. Then populates inbox content:
applications, interview schedules from employers, and one admin announcement.

Run with:
    python manage.py seed_demo            # add data, skip duplicates
    python manage.py seed_demo --wipe     # delete previous demo users first

Email patterns:
    companyname@gmail.com   (e.g. shell@gmail.com)
    firstname.lastname@gmail.com   (e.g. maria.santos@gmail.com)

Password for every account: easyhire2001
"""
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import User
from apps.employers.models import Company, EmployerProfile, EmployerContact
from apps.jobseekers.models import (
    JobseekerProfile, Education, Skill, Certification, WorkExperience, Sector,
)
from apps.jobs.models import (
    JobPosting, JobEducationRequirement, JobSkillRequirement,
    JobCertificationRequirement, JobExperienceRequirement, Application,
)
from apps.admin_panel.models import AdminAnnouncement


PASSWORD = 'easyhire2001'


COMPANIES = [
    {'name': 'Shell',       'slug': 'shell',       'type': 'local',    'nature': 'Oil & Gas Retail',     'address': 'Mandurriao, Iloilo City'},
    {'name': 'Globe',       'slug': 'globe',       'type': 'local',    'nature': 'Telecommunications',   'address': 'Smallville Complex, Mandurriao, Iloilo City'},
    {'name': 'Smart',       'slug': 'smart',       'type': 'local',    'nature': 'Telecommunications',   'address': 'Atria Park District, Mandurriao, Iloilo City'},
    {'name': 'Jollibee',    'slug': 'jollibee',    'type': 'local',    'nature': 'Quick-Service Restaurant', 'address': 'SM City Iloilo, Mandurriao, Iloilo City'},
    {'name': 'SM',          'slug': 'sm',          'type': 'local',    'nature': 'Retail Mall',          'address': 'Diversion Road, Mandurriao, Iloilo City'},
    {'name': 'Robinsons',   'slug': 'robinsons',   'type': 'local',    'nature': 'Retail Mall',          'address': 'Robinsons Place, Iloilo City Proper'},
    {'name': 'PLDT',        'slug': 'pldt',        'type': 'local',    'nature': 'Telecommunications',   'address': 'Iznart Street, Iloilo City Proper'},
    {'name': 'Cebuana',     'slug': 'cebuana',     'type': 'local',    'nature': 'Pawnshop / Remittance', 'address': 'Ledesma Street, Iloilo City Proper'},
    {'name': 'Accenture',   'slug': 'accenture',   'type': 'bpo',      'nature': 'IT Services / BPO',    'address': 'Iloilo Business Park, Mandurriao, Iloilo City'},
    {'name': 'Megaworld',   'slug': 'megaworld',   'type': 'local',    'nature': 'Real Estate',          'address': 'Iloilo Business Park, Mandurriao, Iloilo City'},
]

REPRESENTATIVES = [
    {'first': 'Maria',   'last': 'Santos',     'position': 'HR Manager',                'sex': 'F'},
    {'first': 'Jose',    'last': 'Reyes',      'position': 'Recruitment Officer',       'sex': 'M'},
    {'first': 'Ana',     'last': 'Cruz',       'position': 'Talent Acquisition Lead',   'sex': 'F'},
    {'first': 'Carlos',  'last': 'Garcia',     'position': 'HR Director',               'sex': 'M'},
    {'first': 'Liza',    'last': 'Mendoza',    'position': 'People Operations Head',    'sex': 'F'},
    {'first': 'Ramon',   'last': 'Villanueva', 'position': 'HR Coordinator',            'sex': 'M'},
    {'first': 'Grace',   'last': 'Dela Cruz',  'position': 'Recruitment Specialist',    'sex': 'F'},
    {'first': 'Mark',    'last': 'Bautista',   'position': 'HR Generalist',             'sex': 'M'},
    {'first': 'Sheila',  'last': 'Ramos',      'position': 'Talent Manager',            'sex': 'F'},
    {'first': 'Jerome',  'last': 'Torres',     'position': 'HR Officer',                'sex': 'M'},
]

JOBSEEKERS = [
    {'first': 'Juan',     'last': 'Cruz',       'sex': 'M', 'age': 28, 'barangay': 'Molo'},
    {'first': 'Maria',    'last': 'Garcia',     'sex': 'F', 'age': 24, 'barangay': 'Jaro'},
    {'first': 'Pedro',    'last': 'Reyes',      'sex': 'M', 'age': 35, 'barangay': 'Mandurriao'},
    {'first': 'Ana',      'last': 'Bautista',   'sex': 'F', 'age': 22, 'barangay': 'La Paz'},
    {'first': 'Jose',     'last': 'Villanueva', 'sex': 'M', 'age': 31, 'barangay': 'Arevalo Proper'},
    {'first': 'Liza',     'last': 'Santos',     'sex': 'F', 'age': 26, 'barangay': 'Lapuz Norte'},
    {'first': 'Carlos',   'last': 'Mendoza',    'sex': 'M', 'age': 40, 'barangay': 'San Pedro'},
    {'first': 'Grace',    'last': 'Aquino',     'sex': 'F', 'age': 23, 'barangay': 'Bolilao'},
    {'first': 'Ramon',    'last': 'Torres',     'sex': 'M', 'age': 33, 'barangay': 'Calumpang'},
    {'first': 'Sheila',   'last': 'Aguilar',    'sex': 'F', 'age': 27, 'barangay': 'Buntatala'},
    {'first': 'Marco',    'last': 'Lopez',      'sex': 'M', 'age': 29, 'barangay': 'Tagbac'},
    {'first': 'Cristina', 'last': 'Diaz',       'sex': 'F', 'age': 32, 'barangay': 'Bito-on'},
    {'first': 'Antonio',  'last': 'Flores',     'sex': 'M', 'age': 45, 'barangay': 'Calahunan'},
    {'first': 'Rosa',     'last': 'Marquez',    'sex': 'F', 'age': 25, 'barangay': 'Sambag'},
    {'first': 'Manuel',   'last': 'Ramos',      'sex': 'M', 'age': 38, 'barangay': 'Tabuc Suba'},
    {'first': 'Cecilia',  'last': 'Robles',     'sex': 'F', 'age': 30, 'barangay': 'Quintin Salas'},
    {'first': 'Roberto',  'last': 'Castro',     'sex': 'M', 'age': 36, 'barangay': 'Hibao-an Sur'},
    {'first': 'Teresa',   'last': 'Navarro',    'sex': 'F', 'age': 28, 'barangay': 'San Isidro'},
    {'first': 'Eduardo',  'last': 'Salvador',   'sex': 'M', 'age': 41, 'barangay': 'Ungka I'},
    {'first': 'Luz',      'last': 'Pascual',    'sex': 'F', 'age': 22, 'barangay': 'Magsaysay Village'},
]

# Skill bags per "profession" so jobseekers' resumes line up with real jobs.
SKILL_BAGS = [
    ['Customer Service', 'Communication', 'Microsoft Office', 'Cash Handling'],
    ['Python', 'JavaScript', 'SQL', 'Git', 'HTML/CSS'],
    ['Bookkeeping', 'Microsoft Excel', 'Financial Reporting', 'QuickBooks'],
    ['Patient Care', 'Medical Documentation', 'IV Insertion', 'CPR'],
    ['Sales', 'Customer Service', 'Inventory Management', 'POS Systems'],
    ['Social Media Marketing', 'Copywriting', 'Canva', 'Email Marketing'],
    ['Electrical Wiring', 'Troubleshooting', 'Blueprint Reading'],
    ['Lesson Planning', 'Classroom Management', 'Communication'],
    ['Data Entry', 'Microsoft Office', 'Filing', 'Scheduling'],
    ['Inventory Management', 'Forklift Operation', 'Physical Stamina'],
]

EDU_TEMPLATES = [
    ('bachelor',  'BS Computer Science',     'University of San Agustin'),
    ('bachelor',  'BS Business Administration', 'University of the Philippines Visayas'),
    ('bachelor',  'BS Accountancy',          'Central Philippine University'),
    ('bachelor',  'BS Nursing',              'West Visayas State University'),
    ('bachelor',  'BS Education',            'Iloilo Science and Technology University'),
    ('bachelor',  'BS Marketing',            'University of San Agustin'),
    ('vocational','TESDA Electrical Technology', 'Iloilo TESDA Training Center'),
    ('vocational','TESDA Computer Hardware Servicing', 'Iloilo TESDA Training Center'),
    ('senior_high','TVL — Information & Communication Technology', 'Iloilo National High School'),
    ('senior_high','HUMSS Strand',           'St. Robert\'s International Academy'),
]

EXPERIENCE_TEMPLATES = [
    ('Customer Service Representative', 'Convergys Philippines'),
    ('Sales Associate', 'SM City Iloilo'),
    ('Cashier', 'Robinsons Place Iloilo'),
    ('Administrative Assistant', 'Iloilo Provincial Capitol'),
    ('Junior Developer', 'Megaworld IT Services'),
    ('Teacher', 'St. Therese-MTC Colleges'),
    ('Bookkeeper', 'Iloilo Cooperative Bank'),
    ('Nurse Intern', 'St. Paul\'s Hospital'),
    ('Electrician', 'Iloilo Electric Cooperative'),
    ('Warehouse Staff', 'Megaworld Logistics'),
]

# Subset of seed.py JOB_TEMPLATES — picked to cover a variety of careers.
JOB_TEMPLATES = [
    {'title': 'Customer Service Representative', 'edu': 'senior_high', 'edu_course': '', 'exp_months': 0,
     'skills': ['Communication', 'Customer Service', 'Microsoft Office'],
     'certs': [], 'slots': 5,
     'desc': 'Handle customer inquiries, resolve complaints, and provide product support via phone and email. Shifting schedule. Training provided.'},
    {'title': 'Administrative Assistant', 'edu': 'bachelor', 'edu_course': 'Business Administration', 'exp_months': 12,
     'skills': ['Microsoft Office', 'Data Entry', 'Filing', 'Scheduling'],
     'certs': [], 'slots': 2,
     'desc': 'Provide administrative support to management. Scheduling, correspondence, filing, coordinating office activities.'},
    {'title': 'Registered Nurse', 'edu': 'bachelor', 'edu_course': 'Nursing', 'exp_months': 0,
     'skills': ['Patient Care', 'Medical Documentation', 'IV Insertion'],
     'certs': [('PRC Nursing License', 'Professional Regulation Commission')], 'slots': 3,
     'desc': 'Provide direct patient care in a hospital setting. Assessment, medication administration, and patient education.'},
    {'title': 'Software Developer', 'edu': 'bachelor', 'edu_course': 'Computer Science', 'exp_months': 24,
     'skills': ['Python', 'JavaScript', 'SQL', 'Git'],
     'certs': [], 'slots': 2,
     'desc': 'Design, develop, and maintain web applications. Cross-functional teamwork with product and design.'},
    {'title': 'Accounting Staff', 'edu': 'bachelor', 'edu_course': 'Accountancy', 'exp_months': 12,
     'skills': ['Bookkeeping', 'Microsoft Excel', 'Financial Reporting'],
     'certs': [], 'slots': 2,
     'desc': 'Handle accounts payable/receivable, bookkeeping, bank reconciliation, and monthly financial reporting.'},
    {'title': 'Sales Associate', 'edu': 'senior_high', 'edu_course': '', 'exp_months': 0,
     'skills': ['Sales', 'Customer Service', 'Cash Handling'],
     'certs': [], 'slots': 6,
     'desc': 'Assist customers in product selection, process transactions, and maintain store displays.'},
    {'title': 'Marketing Coordinator', 'edu': 'bachelor', 'edu_course': 'Marketing', 'exp_months': 12,
     'skills': ['Social Media Marketing', 'Copywriting', 'Canva', 'Email Marketing'],
     'certs': [], 'slots': 1,
     'desc': 'Assist in the planning and execution of marketing campaigns across digital and traditional channels.'},
    {'title': 'Electrician', 'edu': 'vocational', 'edu_course': '', 'exp_months': 24,
     'skills': ['Electrical Wiring', 'Troubleshooting', 'Blueprint Reading'],
     'certs': [('TESDA NC II Electrician', 'TESDA')], 'slots': 2,
     'desc': 'Install, maintain, and repair electrical systems in commercial and residential buildings.'},
    {'title': 'IT Support Specialist', 'edu': 'bachelor', 'edu_course': 'Information Technology', 'exp_months': 12,
     'skills': ['Networking', 'Hardware Troubleshooting', 'Windows Server'],
     'certs': [], 'slots': 1,
     'desc': 'Provide technical support to end users. Hardware and software troubleshooting; IT infrastructure maintenance.'},
    {'title': 'Warehouse Staff', 'edu': 'junior_high', 'edu_course': '', 'exp_months': 0,
     'skills': ['Inventory Management', 'Physical Stamina'],
     'certs': [], 'slots': 4,
     'desc': 'Receive, store, and dispatch goods. Maintain inventory records and ensure warehouse cleanliness and safety.'},
]


class Command(BaseCommand):
    help = 'Seed local DB with 20 jobseekers, 10 companies, jobs, and inbox content (passwords: easyhire2001)'

    def add_arguments(self, parser):
        parser.add_argument('--wipe', action='store_true',
            help='Delete previously-seeded demo users (by email pattern) before re-seeding.')

    def handle(self, *args, **opts):
        random.seed(42)  # deterministic output

        if opts['wipe']:
            wipe_count = 0
            for cd in COMPANIES:
                u = User.objects.filter(email=f"{cd['slug']}@gmail.com").first()
                if u: u.delete(); wipe_count += 1
            for jd in JOBSEEKERS:
                e = f"{jd['first'].lower()}.{jd['last'].lower().replace(' ', '')}@gmail.com"
                u = User.objects.filter(email=e).first()
                if u: u.delete(); wipe_count += 1
            self.stdout.write(self.style.WARNING(f'Wiped {wipe_count} demo users.'))

        # ── Companies + reps ──────────────────────────────────────────
        companies = []
        for i, cd in enumerate(COMPANIES):
            rep = REPRESENTATIVES[i]
            email = f"{cd['slug']}@gmail.com"

            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'user_type': User.EMPLOYER,
                    'is_active': True,
                    'consented_to_terms': True,
                    'consented_at': timezone.now(),
                },
            )
            user.set_password(PASSWORD)
            user.user_type = User.EMPLOYER
            user.save()

            company, _ = Company.objects.get_or_create(
                slug=cd['slug'],
                defaults={
                    'name': cd['name'],
                    'type_of_company': cd['type'],
                    'nature_of_company': cd['nature'],
                    'company_email': email,
                    'recruitment_email': email,
                    'main_branch_address': cd['address'],
                    'verification_status': Company.VERIFIED,
                    'verified_at': timezone.now(),
                },
            )

            EmployerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'company': company,
                    'first_name': rep['first'],
                    'last_name': rep['last'],
                    'sex': rep['sex'],
                    'position': rep['position'],
                    'phone': f"0917{random.randint(1000000, 9999999)}",
                    'email': email,
                },
            )
            companies.append(company)
        self.stdout.write(self.style.SUCCESS(f'Companies ready: {len(companies)}'))

        # ── Jobs (2 per company = 20 jobs) ────────────────────────────
        jobs = []
        for i, company in enumerate(companies):
            # Each company gets 2 jobs picked deterministically from the templates
            picks = [JOB_TEMPLATES[(i * 2) % len(JOB_TEMPLATES)],
                     JOB_TEMPLATES[(i * 2 + 1) % len(JOB_TEMPLATES)]]
            for jt in picks:
                job, created = JobPosting.objects.get_or_create(
                    company=company, title=jt['title'],
                    defaults={
                        'description': jt['desc'],
                        'location_type': JobPosting.ILOILO,
                        'barangay_name': company.main_branch_address.split(',')[0].strip(),
                        'city': 'Iloilo City',
                        'slots': jt['slots'],
                        'status': JobPosting.STATUS_OPEN,
                        'contact_email': company.recruitment_email,
                    },
                )
                if created:
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
                jobs.append(job)
        self.stdout.write(self.style.SUCCESS(f'Jobs ready: {len(jobs)}'))

        # ── Jobseekers ────────────────────────────────────────────────
        seekers = []
        today = date.today()
        for i, jd in enumerate(JOBSEEKERS):
            email = f"{jd['first'].lower()}.{jd['last'].lower().replace(' ', '')}@gmail.com"
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

            dob = date(today.year - jd['age'], random.randint(1, 12), random.randint(1, 28))
            profile, p_created = JobseekerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'first_name': jd['first'],
                    'last_name': jd['last'],
                    'sex': jd['sex'],
                    'date_of_birth': dob,
                    'civil_status': random.choice(['single', 'married']),
                    'street_barangay': f"{random.randint(10, 999)} {random.choice(['Iznart', 'Rizal', 'Luna', 'Bonifacio', 'Aldeguer', 'Quezon'])} Street",
                    'barangay': jd['barangay'],
                    'city_municipality': 'Iloilo City',
                    'province': 'Iloilo',
                    'province_code': '063000000',
                    'phone': f"0917{random.randint(1000000, 9999999)}",
                    'contact_email': email,
                    'profile_complete': True,
                    'profile_visibility': 'public',
                    'sector_badge_visibility': 'public',
                    'bio': f"Looking for {random.choice(['full-time', 'part-time', 'remote'])} opportunities in Iloilo City. Hardworking and eager to learn.",
                },
            )
            if p_created:
                # Education
                edu_level, edu_course, edu_inst = random.choice(EDU_TEMPLATES)
                Education.objects.create(
                    profile=profile, level=edu_level, course_degree=edu_course,
                    institution=edu_inst,
                    year_started=today.year - jd['age'] + 18,
                    year_ended=today.year - jd['age'] + 22,
                )
                # Skills: at least 3 (or all of the bag if smaller), up to all of it
                bag = random.choice(SKILL_BAGS)
                n = random.randint(min(3, len(bag)), len(bag))
                for s in random.sample(bag, n):
                    Skill.objects.create(profile=profile, name=s)
                # Experience (0-2 entries)
                for _ in range(random.randint(0, 2)):
                    pos, comp_name = random.choice(EXPERIENCE_TEMPLATES)
                    yr_start = today.year - random.randint(2, jd['age'] - 18 + 1) if jd['age'] > 22 else today.year - 2
                    WorkExperience.objects.create(
                        profile=profile, position=pos, company=comp_name,
                        month_started='January', year_started=yr_start,
                        month_ended='December',  year_ended=yr_start + random.randint(1, 3),
                        description=f"Worked as {pos} at {comp_name}.",
                    )
                # Certification (0-1)
                if random.random() < 0.4:
                    Certification.objects.create(
                        profile=profile,
                        name=random.choice(['First Aid Certification', 'TESDA NC II', 'PRC License', 'Google Digital Garage']),
                        issuing_org=random.choice(['Red Cross', 'TESDA', 'PRC', 'Google']),
                        year_received=today.year - random.randint(1, 5),
                    )
            seekers.append(profile)
        self.stdout.write(self.style.SUCCESS(f'Jobseekers ready: {len(seekers)}'))

        # ── Applications (~30 spread across seekers→jobs) ─────────────
        existing_app_keys = set(Application.objects.values_list('jobseeker_id', 'job_id'))
        app_count = 0
        for seeker in seekers:
            for job in random.sample(jobs, k=random.randint(1, 3)):
                if (seeker.id, job.id) in existing_app_keys:
                    continue
                status = random.choices(
                    [Application.STATUS_PENDING, Application.STATUS_VIEWED,
                     Application.STATUS_ACCEPTED, Application.STATUS_REJECTED],
                    weights=[5, 3, 2, 2], k=1,
                )[0]
                Application.objects.create(
                    jobseeker=seeker, job=job, status=status,
                    message=f"Hi, I'd like to apply for the {job.title} position. I believe my background fits well with what you're looking for.",
                )
                existing_app_keys.add((seeker.id, job.id))
                app_count += 1
        self.stdout.write(self.style.SUCCESS(f'Applications created: {app_count}'))

        # ── Employer contacts (interview invitations) ─────────────────
        contact_count = 0
        target_contacts = 8
        if EmployerContact.objects.count() < target_contacts:
            for _ in range(target_contacts - EmployerContact.objects.count()):
                seeker = random.choice(seekers)
                company = random.choice(companies)
                rep = company.representatives.first()
                if not rep:
                    continue
                interview_at = timezone.now() + timedelta(days=random.randint(2, 14),
                                                          hours=random.randint(9, 16))
                EmployerContact.objects.create(
                    sender=rep.user, company=company, recipient=seeker,
                    kind=EmployerContact.KIND_INTERVIEW,
                    subject=f"Interview invitation — {company.name}",
                    body=(f"Hi {seeker.first_name},\n\n"
                          f"We'd like to invite you to an interview for an open position at {company.name}.\n\n"
                          f"Please confirm by replying to this email whether the proposed date and time work for you.\n\n"
                          f"Thanks,\n{rep.first_name} {rep.last_name}\n{company.name} Recruitment Team"),
                    interview_at=interview_at,
                    interview_location=random.choice([
                        'Google Meet (link to follow)',
                        company.main_branch_address,
                        'Zoom (link to follow)',
                    ]),
                )
                contact_count += 1
        self.stdout.write(self.style.SUCCESS(f'Employer contacts created: {contact_count}'))

        # ── One admin announcement (skip if any already exists) ───────
        if not AdminAnnouncement.objects.exists():
            staff = User.objects.filter(is_staff=True).first()
            AdminAnnouncement.objects.create(
                sender=staff,
                audience=AdminAnnouncement.AUDIENCE_ALL,
                subject='Welcome to EasyHire — Iloilo City PESO is live!',
                body=('Hello Iloilo!\n\n'
                      'EasyHire is the official digital platform of PESO Iloilo City. '
                      'Jobseekers can complete their resume, browse open jobs, and apply directly. '
                      'Employers can post jobs, browse matched candidates, and schedule interviews.\n\n'
                      'For help or feedback, contact peso@iloilocity.gov.ph.\n\n'
                      '— PESO Iloilo City'),
            )
            self.stdout.write(self.style.SUCCESS('Admin announcement created.'))
        else:
            self.stdout.write('Admin announcement already exists — skipping.')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. All accounts use password: {PASSWORD}\n'
            f'Try logging in as e.g. shell@gmail.com (employer) or maria.garcia@gmail.com (jobseeker).'
        ))
