"""Stack ADDITIONAL demo data on top of `seed_demo` — more people, more jobs,
more interactions — with backdated timestamps so analytics look like a live
system rather than a birthday cake.

Idempotent: gated by presence of any User with `@easyhire.extra` email. Re-runs
are no-ops unless --force is passed. Uses get_or_create everywhere, and guards
Applications by unique (jobseeker, job) and EmployerContacts by
(sender, recipient, kind).

Backdating strategy: everything is spread across the LAST 180 DAYS, weighted
slightly toward more recent activity. `auto_now_add` fields are re-written via
Model.objects.filter(pk=...).update(created_at=...) which bypasses the auto set.

Run once from Render Shell:
    python manage.py seed_more

Force a re-seed (only if you know what you're doing — will attempt to add rows
even if the marker is present, but idempotency guards still hold per-row):
    python manage.py seed_more --force

Password for every new account: easyhire2001
"""
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.employers.models import Company, EmployerProfile, EmployerContact
from apps.jobseekers.models import (
    JobseekerProfile, Education, Skill, Certification, WorkExperience,
)
from apps.jobs.models import (
    JobPosting, JobEducationRequirement, JobSkillRequirement,
    JobCertificationRequirement, JobExperienceRequirement, Application,
)


PASSWORD = 'easyhire2001'
EXTRA_DOMAIN = 'easyhire.extra'


def _mark_email_verified(user, email):
    try:
        from allauth.account.models import EmailAddress
    except ImportError:
        return
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={'verified': True, 'primary': True},
    )


def _backdate(model, pk, field, when):
    """Bypass auto_now_add / auto_now to set a specific timestamp."""
    model.objects.filter(pk=pk).update(**{field: when})


def _random_past(days_min=1, days_max=180):
    """Return an aware datetime `days_min..days_max` days ago at a random hour."""
    now = timezone.now()
    delta_days = random.randint(days_min, days_max)
    delta_hours = random.randint(0, 23)
    delta_minutes = random.randint(0, 59)
    return now - timedelta(days=delta_days, hours=delta_hours, minutes=delta_minutes)


# ── Extra companies ────────────────────────────────────────────────────────
EXTRA_COMPANIES = [
    {'name': 'BDO Unibank',      'slug': 'bdo-extra',      'type': 'local', 'nature': 'Banking',                  'address': 'Iznart Street, Iloilo City Proper'},
    {'name': 'Metrobank',        'slug': 'metrobank-extra','type': 'local', 'nature': 'Banking',                  'address': 'Delgado Street, Iloilo City Proper'},
    {'name': 'Landbank',         'slug': 'landbank-extra', 'type': 'local', 'nature': 'Banking',                  'address': 'General Luna Street, Iloilo City Proper'},
    {'name': 'Mercury Drug',     'slug': 'mercury-extra',  'type': 'local', 'nature': 'Retail Pharmacy',          'address': 'Iznart Street, Iloilo City Proper'},
    {'name': 'Iloilo Doctors Hospital', 'slug': 'idh-extra','type': 'local','nature': 'Healthcare / Hospital',    'address': 'West Avenue, Molo, Iloilo City'},
    {'name': 'The Medical City',   'slug': 'tmc-extra',    'type': 'local', 'nature': 'Healthcare / Hospital',    'address': 'Molo, Iloilo City'},
    {'name': 'Concentrix',       'slug': 'concentrix-extra','type': 'bpo', 'nature': 'IT Services / BPO',         'address': 'Iloilo Business Park, Mandurriao'},
    {'name': 'Teleperformance',  'slug': 'teleperf-extra', 'type': 'bpo',   'nature': 'IT Services / BPO',        'address': 'Atria Park District, Mandurriao'},
    {'name': 'GCash',            'slug': 'gcash-extra',    'type': 'local', 'nature': 'Fintech',                  'address': 'Smallville Complex, Mandurriao'},
    {'name': 'Ayala Land',       'slug': 'ayala-extra',    'type': 'local', 'nature': 'Real Estate',              'address': 'Iloilo Business Park, Mandurriao'},
    {'name': 'Puregold',         'slug': 'puregold-extra', 'type': 'local', 'nature': 'Retail Grocery',           'address': 'La Paz Public Market Area, Iloilo City'},
    {'name': 'Gaisano Capital',  'slug': 'gaisano-extra',  'type': 'local', 'nature': 'Retail Mall',              'address': 'de Leon Street, Iloilo City Proper'},
    {'name': 'Chowking',         'slug': 'chowking-extra', 'type': 'local', 'nature': 'Quick-Service Restaurant', 'address': 'SM City Iloilo, Mandurriao'},
    {'name': 'Mang Inasal',      'slug': 'manginasal-extra','type': 'local','nature': 'Quick-Service Restaurant', 'address': 'Robinsons Place Iloilo, Iloilo City Proper'},
    {'name': 'Iloilo Cooperative Bank', 'slug': 'icb-extra','type': 'local','nature': 'Banking',                  'address': 'Iznart Street, Iloilo City Proper'},
]

EXTRA_REPS = [
    {'first': 'Diana',   'last': 'Salcedo',   'position': 'HR Manager',            'sex': 'F'},
    {'first': 'Rex',     'last': 'Palmares',  'position': 'Recruitment Head',      'sex': 'M'},
    {'first': 'Nena',    'last': 'Alcantara', 'position': 'HR Officer',            'sex': 'F'},
    {'first': 'Vince',   'last': 'Bacus',     'position': 'Talent Acquisition',    'sex': 'M'},
    {'first': 'Amie',    'last': 'Cabreros',  'position': 'People Operations',     'sex': 'F'},
    {'first': 'Dante',   'last': 'Espino',    'position': 'HR Coordinator',        'sex': 'M'},
    {'first': 'Belle',   'last': 'Fajardo',   'position': 'Recruitment Officer',   'sex': 'F'},
    {'first': 'Gino',    'last': 'Hipolito',  'position': 'HR Director',           'sex': 'M'},
    {'first': 'Jing',    'last': 'Ilagan',    'position': 'Talent Manager',        'sex': 'F'},
    {'first': 'Kris',    'last': 'Jimenez',   'position': 'HR Generalist',         'sex': 'F'},
    {'first': 'Leo',     'last': 'Kabigting', 'position': 'Recruitment Specialist','sex': 'M'},
    {'first': 'Mai',     'last': 'Lagunilla', 'position': 'HR Manager',            'sex': 'F'},
    {'first': 'Noel',    'last': 'Macatangay','position': 'HR Officer',            'sex': 'M'},
    {'first': 'Pam',     'last': 'Nolasco',   'position': 'People Operations',     'sex': 'F'},
    {'first': 'Quintin', 'last': 'Ocampo',    'position': 'Talent Acquisition',    'sex': 'M'},
]

# ── Extra jobseekers ───────────────────────────────────────────────────────
EXTRA_JOBSEEKERS = [
    {'first': 'Aaron',    'last': 'Ababa',      'sex': 'M', 'age': 24, 'barangay': 'Molo'},
    {'first': 'Beatrice', 'last': 'Cabana',     'sex': 'F', 'age': 27, 'barangay': 'Jaro'},
    {'first': 'Cirilo',   'last': 'Delantar',   'sex': 'M', 'age': 30, 'barangay': 'La Paz'},
    {'first': 'Dianne',   'last': 'Estrellado', 'sex': 'F', 'age': 22, 'barangay': 'Mandurriao'},
    {'first': 'Emil',     'last': 'Fugoso',     'sex': 'M', 'age': 26, 'barangay': 'Arevalo Proper'},
    {'first': 'Fatima',   'last': 'Gorriceta',  'sex': 'F', 'age': 25, 'barangay': 'Lapuz Norte'},
    {'first': 'Gian',     'last': 'Habaluyas',  'sex': 'M', 'age': 33, 'barangay': 'San Pedro'},
    {'first': 'Heidi',    'last': 'Isulat',     'sex': 'F', 'age': 29, 'barangay': 'Bolilao'},
    {'first': 'Ivan',     'last': 'Jamora',     'sex': 'M', 'age': 39, 'barangay': 'Calumpang'},
    {'first': 'Jamie',    'last': 'Kabigting',  'sex': 'F', 'age': 21, 'barangay': 'Buntatala'},
    {'first': 'Kevin',    'last': 'Lachica',    'sex': 'M', 'age': 28, 'barangay': 'Tagbac'},
    {'first': 'Laila',    'last': 'Mabolo',     'sex': 'F', 'age': 34, 'barangay': 'Bito-on'},
    {'first': 'Miguel',   'last': 'Naguit',     'sex': 'M', 'age': 42, 'barangay': 'Calahunan'},
    {'first': 'Nadia',    'last': 'Ochoa',      'sex': 'F', 'age': 23, 'barangay': 'Sambag'},
    {'first': 'Oscar',    'last': 'Panganiban', 'sex': 'M', 'age': 37, 'barangay': 'Tabuc Suba'},
    {'first': 'Precious', 'last': 'Quimson',    'sex': 'F', 'age': 26, 'barangay': 'Quintin Salas'},
    {'first': 'Reggie',   'last': 'Rimando',    'sex': 'M', 'age': 31, 'barangay': 'Hibao-an Sur'},
    {'first': 'Sylvia',   'last': 'Sagrado',    'sex': 'F', 'age': 27, 'barangay': 'San Isidro'},
    {'first': 'Tomas',    'last': 'Tabuada',    'sex': 'M', 'age': 45, 'barangay': 'Ungka I'},
    {'first': 'Ursula',   'last': 'Ubaldo',     'sex': 'F', 'age': 22, 'barangay': 'Magsaysay Village'},
    {'first': 'Victor',   'last': 'Valino',     'sex': 'M', 'age': 32, 'barangay': 'Molo'},
    {'first': 'Winifred', 'last': 'Wagan',      'sex': 'F', 'age': 24, 'barangay': 'Jaro'},
    {'first': 'Xander',   'last': 'Ximena',     'sex': 'M', 'age': 29, 'barangay': 'La Paz'},
    {'first': 'Yasmin',   'last': 'Ybanez',     'sex': 'F', 'age': 30, 'barangay': 'Mandurriao'},
    {'first': 'Zeke',     'last': 'Zamora',     'sex': 'M', 'age': 26, 'barangay': 'Arevalo Proper'},
    {'first': 'Alice',    'last': 'Banayad',    'sex': 'F', 'age': 25, 'barangay': 'Lapuz Norte'},
    {'first': 'Bruno',    'last': 'Cariaga',    'sex': 'M', 'age': 36, 'barangay': 'San Pedro'},
    {'first': 'Celia',    'last': 'Duenas',     'sex': 'F', 'age': 28, 'barangay': 'Bolilao'},
    {'first': 'Dennis',   'last': 'Escoto',     'sex': 'M', 'age': 41, 'barangay': 'Calumpang'},
    {'first': 'Erika',    'last': 'Fadullon',   'sex': 'F', 'age': 23, 'barangay': 'Buntatala'},
]

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
    ['Cooking', 'Food Safety', 'Menu Planning', 'Customer Service'],
    ['Basic Networking', 'Windows Server', 'Active Directory'],
]

EDU_TEMPLATES = [
    ('bachelor',   'BS Computer Science',           'University of San Agustin'),
    ('bachelor',   'BS Business Administration',    'University of the Philippines Visayas'),
    ('bachelor',   'BS Accountancy',                'Central Philippine University'),
    ('bachelor',   'BS Nursing',                    'West Visayas State University'),
    ('bachelor',   'BS Education',                  'Iloilo Science and Technology University'),
    ('bachelor',   'BS Marketing',                  'University of San Agustin'),
    ('bachelor',   'BS Information Technology',     'Central Philippine University'),
    ('bachelor',   'BS Hotel and Restaurant Management','John B. Lacson Foundation Maritime University'),
    ('vocational', 'TESDA Electrical Technology',   'Iloilo TESDA Training Center'),
    ('vocational', 'TESDA Computer Hardware Servicing','Iloilo TESDA Training Center'),
    ('vocational', 'TESDA Bookkeeping NC III',      'Iloilo TESDA Training Center'),
    ('senior_high','TVL — Information & Communication Technology','Iloilo National High School'),
    ('senior_high','HUMSS Strand',                  'St. Robert\'s International Academy'),
    ('senior_high','ABM Strand',                    'Iloilo Central Commercial High School'),
]

EXPERIENCE_TEMPLATES = [
    ('Customer Service Representative', 'Convergys Philippines'),
    ('Sales Associate',                 'SM City Iloilo'),
    ('Cashier',                         'Robinsons Place Iloilo'),
    ('Administrative Assistant',        'Iloilo Provincial Capitol'),
    ('Junior Developer',                'Megaworld IT Services'),
    ('Teacher',                         'St. Therese-MTC Colleges'),
    ('Bookkeeper',                      'Iloilo Cooperative Bank'),
    ('Nurse Intern',                    'St. Paul\'s Hospital'),
    ('Electrician',                     'Iloilo Electric Cooperative'),
    ('Warehouse Staff',                 'Megaworld Logistics'),
    ('Kitchen Staff',                   'Jollibee Iloilo'),
    ('Front Office Clerk',              'Days Hotel Iloilo'),
]

EXTRA_JOB_TEMPLATES = [
    {'title': 'Bank Teller', 'edu': 'bachelor', 'edu_course': 'Business Administration', 'exp_months': 6,
     'skills': ['Customer Service', 'Cash Handling', 'Microsoft Office'],
     'certs': [], 'slots': 3,
     'desc': 'Serve customers at the bank counter, process transactions, and handle inquiries. Full-time, on-site.'},
    {'title': 'Pharmacy Assistant', 'edu': 'senior_high', 'edu_course': '', 'exp_months': 0,
     'skills': ['Customer Service', 'Inventory Management', 'Communication'],
     'certs': [], 'slots': 4,
     'desc': 'Assist licensed pharmacists in dispensing medication and managing pharmacy stock.'},
    {'title': 'Medical Records Clerk', 'edu': 'senior_high', 'edu_course': '', 'exp_months': 6,
     'skills': ['Data Entry', 'Medical Documentation', 'Filing'],
     'certs': [], 'slots': 2,
     'desc': 'Organize and maintain patient records at the hospital records office. Confidential handling required.'},
    {'title': 'Call Center Agent (Voice)', 'edu': 'senior_high', 'edu_course': '', 'exp_months': 0,
     'skills': ['Communication', 'Customer Service', 'Microsoft Office'],
     'certs': [], 'slots': 10,
     'desc': 'Handle inbound and outbound calls for US and Australian accounts. Shifting schedule, on-site.'},
    {'title': 'Chat Support Agent', 'edu': 'senior_high', 'edu_course': '', 'exp_months': 0,
     'skills': ['Communication', 'Customer Service', 'Data Entry'],
     'certs': [], 'slots': 6,
     'desc': 'Respond to customer messages via chat and email. No calls. Fixed graveyard schedule.'},
    {'title': 'IT Helpdesk', 'edu': 'bachelor', 'edu_course': 'Information Technology', 'exp_months': 6,
     'skills': ['Basic Networking', 'Windows Server', 'Hardware Troubleshooting'],
     'certs': [], 'slots': 2,
     'desc': 'First-line support for internal IT tickets: accounts, printers, VPN, laptop setup.'},
    {'title': 'Kitchen Crew', 'edu': 'junior_high', 'edu_course': '', 'exp_months': 0,
     'skills': ['Cooking', 'Food Safety', 'Customer Service'],
     'certs': [], 'slots': 5,
     'desc': 'Prepare food orders, maintain kitchen cleanliness, and follow health and safety protocols.'},
    {'title': 'Store Cashier', 'edu': 'senior_high', 'edu_course': '', 'exp_months': 0,
     'skills': ['Cash Handling', 'Customer Service', 'POS Systems'],
     'certs': [], 'slots': 8,
     'desc': 'Handle checkout counter — scan items, process payments, issue receipts. Rotating shifts.'},
    {'title': 'Property Sales Associate', 'edu': 'bachelor', 'edu_course': 'Marketing', 'exp_months': 12,
     'skills': ['Sales', 'Communication', 'Customer Service'],
     'certs': [], 'slots': 3,
     'desc': 'Sell residential and commercial property. Commission-based on top of base salary.'},
    {'title': 'Registered Nurse (ER)', 'edu': 'bachelor', 'edu_course': 'Nursing', 'exp_months': 12,
     'skills': ['Patient Care', 'IV Insertion', 'Medical Documentation'],
     'certs': [('PRC Nursing License', 'Professional Regulation Commission')], 'slots': 2,
     'desc': 'Provide emergency nursing care in a fast-paced ER setting. Rotating 12-hour shifts.'},
]


class Command(BaseCommand):
    help = 'Add MORE demo users, jobs, and interactions (backdated up to 180 days) on top of seed_demo.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
            help='Run even if extra seed marker (@easyhire.extra users) exists.')

    def handle(self, *args, **opts):
        random.seed(7)  # deterministic

        # ── Idempotency guard ─────────────────────────────────────────
        marker_exists = User.objects.filter(email__endswith=f'@{EXTRA_DOMAIN}').exists()
        if marker_exists and not opts['force']:
            self.stdout.write(self.style.WARNING(
                f'Extra seed already applied (@{EXTRA_DOMAIN} users exist). '
                f'Re-run with --force to attempt again — per-row guards still hold.'
            ))
            return

        # ── Backdated companies + reps ────────────────────────────────
        extra_companies = []
        for i, cd in enumerate(EXTRA_COMPANIES):
            rep = EXTRA_REPS[i]
            email = f"{cd['slug']}@{EXTRA_DOMAIN}"

            user, u_created = User.objects.get_or_create(
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
            _mark_email_verified(user, email)

            joined_at = _random_past(days_min=30, days_max=180)
            _backdate(User, user.pk, 'created_at', joined_at)

            company, c_created = Company.objects.get_or_create(
                slug=cd['slug'],
                defaults={
                    'name': cd['name'],
                    'type_of_company': cd['type'],
                    'nature_of_company': cd['nature'],
                    'company_email': email,
                    'recruitment_email': email,
                    'main_branch_address': cd['address'],
                    'verification_status': Company.VERIFIED,
                    'verified_at': joined_at,
                },
            )
            _backdate(Company, company.pk, 'created_at', joined_at)

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
            extra_companies.append(company)
        self.stdout.write(self.style.SUCCESS(
            f'Extra companies ready: {len(extra_companies)}'
        ))

        # ── Backdated jobs (2-4 per new company) ──────────────────────
        extra_jobs = []
        for i, company in enumerate(extra_companies):
            n_jobs = random.randint(2, 4)
            picks = random.sample(EXTRA_JOB_TEMPLATES, k=n_jobs)
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
                    posted_at = _random_past(days_min=7, days_max=170)
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
                extra_jobs.append(job)
        self.stdout.write(self.style.SUCCESS(f'Extra jobs ready: {len(extra_jobs)}'))

        # ── Backdated jobseekers ──────────────────────────────────────
        extra_seekers = []
        today = date.today()
        for jd in EXTRA_JOBSEEKERS:
            email = (
                f"{jd['first'].lower()}."
                f"{jd['last'].lower().replace(' ', '')}"
                f"@{EXTRA_DOMAIN}"
            )
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

            signed_up = _random_past(days_min=5, days_max=180)
            _backdate(User, user.pk, 'created_at', signed_up)

            dob = date(today.year - jd['age'], random.randint(1, 12), random.randint(1, 28))
            profile, p_created = JobseekerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'first_name': jd['first'],
                    'last_name': jd['last'],
                    'sex': jd['sex'],
                    'date_of_birth': dob,
                    # Weighted mix across all 5 civil statuses — see seed_demo.py
                    # for the rationale on the specific weights used here.
                    'civil_status': random.choices(
                        ['single', 'married', 'widowed', 'separated', 'annulled'],
                        weights=[55, 30, 6, 6, 3], k=1,
                    )[0],
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
            _backdate(JobseekerProfile, profile.pk, 'created_at', signed_up)

            if p_created:
                edu_level, edu_course, edu_inst = random.choice(EDU_TEMPLATES)
                Education.objects.create(
                    profile=profile, level=edu_level, course_degree=edu_course,
                    institution=edu_inst,
                    year_started=today.year - jd['age'] + 18,
                    year_ended=today.year - jd['age'] + 22,
                )
                bag = random.choice(SKILL_BAGS)
                n = random.randint(min(3, len(bag)), len(bag))
                for s in random.sample(bag, n):
                    Skill.objects.create(profile=profile, name=s)
                for _ in range(random.randint(0, 2)):
                    pos, comp_name = random.choice(EXPERIENCE_TEMPLATES)
                    yr_start = today.year - random.randint(2, jd['age'] - 18 + 1) if jd['age'] > 22 else today.year - 2
                    WorkExperience.objects.create(
                        profile=profile, position=pos, company=comp_name,
                        month_started='January', year_started=yr_start,
                        month_ended='December', year_ended=yr_start + random.randint(1, 3),
                        description=f"Worked as {pos} at {comp_name}.",
                    )
                if random.random() < 0.4:
                    Certification.objects.create(
                        profile=profile,
                        name=random.choice(['First Aid Certification', 'TESDA NC II', 'PRC License', 'Google Digital Garage']),
                        issuing_org=random.choice(['Red Cross', 'TESDA', 'PRC', 'Google']),
                        year_received=today.year - random.randint(1, 5),
                    )
            extra_seekers.append(profile)
        self.stdout.write(self.style.SUCCESS(f'Extra jobseekers ready: {len(extra_seekers)}'))

        # ── Applications (backdated, mixed statuses, some HIRED) ──────
        # Cast a wide net: all extra seekers apply to a mix of extra + existing jobs.
        all_jobs = list(JobPosting.objects.all())
        existing_app_keys = set(Application.objects.values_list('jobseeker_id', 'job_id'))
        app_count = 0
        hire_count = 0

        for seeker in extra_seekers:
            n_apps = random.randint(2, 6)
            for job in random.sample(all_jobs, k=min(n_apps, len(all_jobs))):
                if (seeker.id, job.id) in existing_app_keys:
                    continue
                status = random.choices(
                    [Application.STATUS_PENDING, Application.STATUS_VIEWED,
                     Application.STATUS_ACCEPTED, Application.STATUS_REJECTED,
                     Application.STATUS_HIRED],
                    weights=[6, 4, 3, 3, 2], k=1,
                )[0]

                applied_at = _random_past(days_min=1, days_max=170)
                app = Application.objects.create(
                    jobseeker=seeker, job=job, status=status,
                    message=(f"Hi, I'd like to apply for the {job.title} position. "
                             f"I believe my background fits well with what you're looking for."),
                )
                _backdate(Application, app.pk, 'created_at', applied_at)

                if status == Application.STATUS_HIRED:
                    # Hire happens 3-30 days after application
                    hired_at = applied_at + timedelta(
                        days=random.randint(3, 30),
                        hours=random.randint(0, 12),
                    )
                    if hired_at > timezone.now():
                        hired_at = timezone.now() - timedelta(days=1)
                    Application.objects.filter(pk=app.pk).update(hired_at=hired_at)
                    hire_count += 1

                existing_app_keys.add((seeker.id, job.id))
                app_count += 1

        # Also give some hires to existing seed_demo seekers so analytics
        # aren't lopsided toward the new batch.
        legacy_seekers = list(JobseekerProfile.objects.exclude(
            user__email__endswith=f'@{EXTRA_DOMAIN}'
        ))
        for seeker in random.sample(legacy_seekers, k=min(10, len(legacy_seekers))):
            job = random.choice(all_jobs)
            if (seeker.id, job.id) in existing_app_keys:
                continue
            applied_at = _random_past(days_min=10, days_max=170)
            app = Application.objects.create(
                jobseeker=seeker, job=job, status=Application.STATUS_HIRED,
                message=f"Hi, I'd like to apply for the {job.title} position.",
            )
            _backdate(Application, app.pk, 'created_at', applied_at)
            hired_at = applied_at + timedelta(days=random.randint(3, 30))
            if hired_at > timezone.now():
                hired_at = timezone.now() - timedelta(days=1)
            Application.objects.filter(pk=app.pk).update(hired_at=hired_at)
            existing_app_keys.add((seeker.id, job.id))
            app_count += 1
            hire_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Applications created: {app_count} (of which {hire_count} hired)'
        ))

        # ── Employer contacts (interview invitations, backdated) ──────
        contact_count = 0
        target_new_contacts = 25
        all_companies = list(Company.objects.all())
        all_seekers_for_contact = list(JobseekerProfile.objects.all())

        for _ in range(target_new_contacts):
            seeker = random.choice(all_seekers_for_contact)
            company = random.choice(all_companies)
            rep = company.representatives.first()
            if not rep:
                continue
            # Skip if this rep already contacted this seeker with an interview.
            if EmployerContact.objects.filter(
                sender=rep.user, recipient=seeker,
                kind=EmployerContact.KIND_INTERVIEW,
            ).exists():
                continue

            sent_at = _random_past(days_min=1, days_max=150)
            interview_at = sent_at + timedelta(
                days=random.randint(3, 20),
                hours=random.randint(9, 16),
            )
            contact = EmployerContact.objects.create(
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
            _backdate(EmployerContact, contact.pk, 'sent_at', sent_at)
            contact_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Employer contacts created: {contact_count}'
        ))

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Extra data seeded with backdated timestamps '
            f'spread across the last ~180 days. Password for new '
            f'accounts: {PASSWORD}'
        ))
