import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from apps.accounts.models import User
from apps.employers.models import Company, EmployerProfile
from apps.jobseekers.models import (
    JobseekerProfile, Education, Skill,
    Certification, WorkExperience, Sector
)
from apps.jobs.models import (
    JobPosting, JobEducationRequirement,
    JobSkillRequirement, JobCertificationRequirement,
    JobExperienceRequirement
)


# ── Seed data ──────────────────────────────────────────────────────────────────

COMPANIES = [
    {"name": "Iloilo Central Hospital", "nature": "Hospital", "type": "local"},
    {"name": "SM City Iloilo", "nature": "Retail Mall", "type": "local"},
    {"name": "Convergys Philippines", "nature": "BPO / Call Center", "type": "bpo"},
    {"name": "Iloilo Science and Technology University", "nature": "University", "type": "local"},
    {"name": "Globe Telecom Iloilo", "nature": "Telecommunications", "type": "local"},
    {"name": "Robinsons Place Iloilo", "nature": "Retail Mall", "type": "local"},
    {"name": "Accenture Iloilo", "nature": "IT Services / BPO", "type": "bpo"},
    {"name": "Department of Health Region VI", "nature": "Government Agency", "type": "local"},
    {"name": "Iloilo Merchant Marine School", "nature": "Maritime School", "type": "overseas"},
    {"name": "Megaworld Iloilo", "nature": "Real Estate", "type": "local"},
]

REPRESENTATIVES = [
    {"first": "Maria", "last": "Santos", "position": "HR Manager"},
    {"first": "Jose", "last": "Reyes", "position": "Recruitment Officer"},
    {"first": "Ana", "last": "Cruz", "position": "Talent Acquisition Lead"},
    {"first": "Carlos", "last": "Garcia", "position": "HR Director"},
    {"first": "Liza", "last": "Mendoza", "position": "People Operations Head"},
    {"first": "Ramon", "last": "Villanueva", "position": "HR Coordinator"},
    {"first": "Grace", "last": "Dela Cruz", "position": "Recruitment Specialist"},
    {"first": "Mark", "last": "Bautista", "position": "HR Generalist"},
    {"first": "Sheila", "last": "Ramos", "position": "Talent Manager"},
    {"first": "Jerome", "last": "Torres", "position": "HR Officer"},
]

JOB_TEMPLATES = [
    {
        "title": "Customer Service Representative",
        "description": "Handle customer inquiries, resolve complaints, and provide product support via phone and email. Must be able to work in a fast-paced environment with shifting schedules.",
        "edu_level": "senior_high",
        "exp_years": 0,
        "skills": ["Communication", "Microsoft Office", "Customer Service"],
        "certs": [],
    },
    {
        "title": "Administrative Assistant",
        "description": "Provide administrative support to management including scheduling, correspondence, filing, and coordinating office activities.",
        "edu_level": "bachelor",
        "edu_course": "Business Administration",
        "exp_years": 1,
        "skills": ["Microsoft Office", "Data Entry", "Communication", "Filing"],
        "certs": [],
    },
    {
        "title": "Registered Nurse",
        "description": "Provide direct patient care in a hospital setting. Responsibilities include assessment, medication administration, and patient education.",
        "edu_level": "bachelor",
        "edu_course": "Nursing",
        "exp_years": 0,
        "skills": ["Patient Care", "Medical Documentation", "IV Insertion"],
        "certs": [{"name": "PRC Nursing License", "org": "Professional Regulation Commission"}],
    },
    {
        "title": "Software Developer",
        "description": "Design, develop, and maintain web applications. Work with cross-functional teams to deliver high-quality software solutions.",
        "edu_level": "bachelor",
        "edu_course": "Computer Science",
        "exp_years": 2,
        "skills": ["Python", "JavaScript", "SQL", "Git"],
        "certs": [],
    },
    {
        "title": "Accounting Staff",
        "description": "Handle accounts payable/receivable, bookkeeping, bank reconciliation, and financial reporting.",
        "edu_level": "bachelor",
        "edu_course": "Accountancy",
        "exp_years": 1,
        "skills": ["Bookkeeping", "Microsoft Excel", "Financial Reporting"],
        "certs": [{"name": "CPA License", "org": "Professional Regulation Commission"}],
    },
    {
        "title": "Sales Associate",
        "description": "Assist customers in product selection, process transactions, and maintain store displays. Meet monthly sales targets.",
        "edu_level": "senior_high",
        "exp_years": 0,
        "skills": ["Sales", "Customer Service", "Cash Handling"],
        "certs": [],
    },
    {
        "title": "Data Analyst",
        "description": "Analyze large datasets to identify trends and provide actionable insights. Create dashboards and reports for management.",
        "edu_level": "bachelor",
        "edu_course": "Statistics",
        "exp_years": 2,
        "skills": ["Python", "SQL", "Excel", "Data Visualization"],
        "certs": [],
    },
    {
        "title": "Marketing Coordinator",
        "description": "Assist in the planning and execution of marketing campaigns across digital and traditional channels.",
        "edu_level": "bachelor",
        "edu_course": "Marketing",
        "exp_years": 1,
        "skills": ["Social Media Marketing", "Copywriting", "Canva", "Email Marketing"],
        "certs": [],
    },
    {
        "title": "Security Guard",
        "description": "Maintain security and safety of company premises. Monitor CCTV, conduct rounds, and respond to incidents.",
        "edu_level": "junior_high",
        "exp_years": 0,
        "skills": ["Surveillance", "Report Writing", "First Aid"],
        "certs": [{"name": "SOSIA License", "org": "PNP"}],
    },
    {
        "title": "Electrician",
        "description": "Install, maintain, and repair electrical systems in commercial and residential buildings.",
        "edu_level": "vocational",
        "exp_years": 2,
        "skills": ["Electrical Wiring", "Troubleshooting", "Blueprint Reading"],
        "certs": [{"name": "TESDA NC II Electrician", "org": "TESDA"}],
    },
    {
        "title": "Seafarer / Ordinary Seaman",
        "description": "Perform deck operations aboard commercial vessels. Duties include maintenance, cargo handling, and safety drills.",
        "edu_level": "vocational",
        "exp_years": 0,
        "skills": ["Seamanship", "Cargo Handling", "Safety Procedures"],
        "certs": [
            {"name": "STCW Basic Safety Training", "org": "MARINA"},
            {"name": "Able Seaman Certificate", "org": "MARINA"},
        ],
    },
    {
        "title": "Teacher / Instructor",
        "description": "Facilitate learning in assigned subject areas. Prepare lesson plans, evaluate student performance, and communicate with parents.",
        "edu_level": "bachelor",
        "edu_course": "Education",
        "exp_years": 0,
        "skills": ["Lesson Planning", "Classroom Management", "Communication"],
        "certs": [{"name": "PRC Teacher License", "org": "Professional Regulation Commission"}],
    },
    {
        "title": "Warehouse Staff",
        "description": "Receive, store, and dispatch goods. Maintain inventory records and ensure warehouse cleanliness and safety.",
        "edu_level": "junior_high",
        "exp_years": 0,
        "skills": ["Inventory Management", "Forklift Operation", "Physical Stamina"],
        "certs": [],
    },
    {
        "title": "IT Support Specialist",
        "description": "Provide technical support to end users. Troubleshoot hardware and software issues and maintain IT infrastructure.",
        "edu_level": "bachelor",
        "edu_course": "Information Technology",
        "exp_years": 1,
        "skills": ["Hardware Troubleshooting", "Networking", "Windows OS", "Help Desk Support"],
        "certs": [],
    },
    {
        "title": "Cook / Kitchen Staff",
        "description": "Prepare and cook food according to menu specifications. Maintain kitchen cleanliness and follow food safety standards.",
        "edu_level": "vocational",
        "exp_years": 1,
        "skills": ["Food Preparation", "Knife Skills", "Food Safety", "Menu Planning"],
        "certs": [{"name": "Food Handler's Certificate", "org": "DOH"}],
    },
]

JOBSEEKERS = [
    {
        "first": "Juan", "last": "dela Cruz", "sex": "M",
        "edu_level": "bachelor", "edu_course": "Computer Science",
        "skills": ["Python", "JavaScript", "SQL", "Git"],
        "exp_years": 3, "sectors": [],
    },
    {
        "first": "Maria", "last": "Reyes", "sex": "F",
        "edu_level": "bachelor", "edu_course": "Nursing",
        "skills": ["Patient Care", "Medical Documentation", "IV Insertion"],
        "certs": [{"name": "PRC Nursing License", "org": "Professional Regulation Commission"}],
        "exp_years": 1, "sectors": ["fresh_graduate"],
    },
    {
        "first": "Carlo", "last": "Santos", "sex": "M",
        "edu_level": "senior_high",
        "skills": ["Customer Service", "Communication", "Microsoft Office"],
        "exp_years": 0, "sectors": ["fresh_graduate"],
    },
    {
        "first": "Ana", "last": "Villanueva", "sex": "F",
        "edu_level": "bachelor", "edu_course": "Accountancy",
        "skills": ["Bookkeeping", "Microsoft Excel", "Financial Reporting"],
        "certs": [{"name": "CPA License", "org": "Professional Regulation Commission"}],
        "exp_years": 2, "sectors": [],
    },
    {
        "first": "Ramon", "last": "Guzman", "sex": "M",
        "edu_level": "vocational",
        "skills": ["Electrical Wiring", "Troubleshooting", "Blueprint Reading"],
        "certs": [{"name": "TESDA NC II Electrician", "org": "TESDA"}],
        "exp_years": 4, "sectors": ["tesda_graduate"],
    },
    {
        "first": "Liza", "last": "Flores", "sex": "F",
        "edu_level": "bachelor", "edu_course": "Education",
        "skills": ["Lesson Planning", "Classroom Management", "Communication"],
        "certs": [{"name": "PRC Teacher License", "org": "Professional Regulation Commission"}],
        "exp_years": 2, "sectors": [],
    },
    {
        "first": "Mark", "last": "Aquino", "sex": "M",
        "edu_level": "bachelor", "edu_course": "Marketing",
        "skills": ["Social Media Marketing", "Copywriting", "Canva"],
        "exp_years": 1, "sectors": ["fresh_graduate"],
    },
    {
        "first": "Grace", "last": "Mendoza", "sex": "F",
        "edu_level": "junior_high",
        "skills": ["Customer Service", "Cash Handling", "Sales"],
        "exp_years": 0, "sectors": ["osy"],
    },
    {
        "first": "Jerome", "last": "Bautista", "sex": "M",
        "edu_level": "vocational",
        "skills": ["Seamanship", "Cargo Handling", "Safety Procedures"],
        "certs": [
            {"name": "STCW Basic Safety Training", "org": "MARINA"},
            {"name": "Able Seaman Certificate", "org": "MARINA"},
        ],
        "exp_years": 0, "sectors": ["tesda_graduate"],
    },
    {
        "first": "Sheila", "last": "Torres", "sex": "F",
        "edu_level": "bachelor", "edu_course": "Business Administration",
        "skills": ["Microsoft Office", "Data Entry", "Communication"],
        "exp_years": 2, "sectors": [],
    },
    {
        "first": "Patrick", "last": "Ramos", "sex": "M",
        "edu_level": "bachelor", "edu_course": "Information Technology",
        "skills": ["Hardware Troubleshooting", "Networking", "Windows OS"],
        "exp_years": 1, "sectors": [],
    },
    {
        "first": "Claire", "last": "Lopez", "sex": "F",
        "edu_level": "senior_high",
        "skills": ["Inventory Management", "Physical Stamina", "Teamwork"],
        "exp_years": 0, "sectors": ["fresh_graduate"],
    },
    {
        "first": "Ryan", "last": "Castillo", "sex": "M",
        "edu_level": "bachelor", "edu_course": "Statistics",
        "skills": ["Python", "SQL", "Excel", "Data Visualization"],
        "exp_years": 2, "sectors": [],
    },
    {
        "first": "Nicole", "last": "Hernandez", "sex": "F",
        "edu_level": "vocational",
        "skills": ["Food Preparation", "Food Safety", "Knife Skills"],
        "certs": [{"name": "Food Handler's Certificate", "org": "DOH"}],
        "exp_years": 1, "sectors": ["tesda_graduate"],
    },
    {
        "first": "Daniel", "last": "Padilla", "sex": "M",
        "edu_level": "junior_high",
        "skills": ["Surveillance", "Report Writing", "First Aid"],
        "certs": [{"name": "SOSIA License", "org": "PNP"}],
        "exp_years": 3, "sectors": [],
    },
]


class Command(BaseCommand):
    help = 'Seed the database with dummy employers, jobs, and jobseekers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing seeded data before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing seeded data...')
            User.objects.filter(email__endswith='@seed.easyhire').delete()
            Company.objects.filter(slug__startswith='seed-').delete()
            self.stdout.write(self.style.SUCCESS('Cleared!'))

        self.stdout.write('Seeding employers...')
        self._seed_employers()

        self.stdout.write('Seeding jobseekers...')
        self._seed_jobseekers()

        self.stdout.write(self.style.SUCCESS(
            f'Done! {len(COMPANIES)} companies, {len(JOBSEEKERS)} jobseekers seeded.'
        ))

    def _seed_employers(self):
        from datetime import date

        for i, company_data in enumerate(COMPANIES):
            email = f"employer{i+1}@seed.easyhire"

            if User.objects.filter(email=email).exists():
                self.stdout.write(f'  Skipping {email} (already exists)')
                continue

            # Create user
            user = User.objects.create_user(
                email=email,
                password='Seed@1234',
                user_type=User.EMPLOYER,
                consented_to_terms=True,
                consented_at=timezone.now(),
            )

            # Create company
            slug = f"seed-{slugify(company_data['name'])}"
            company = Company.objects.create(
                name=company_data['name'],
                slug=slug,
                type_of_company=company_data['type'],
                nature_of_company=company_data['nature'],
                main_branch_address=f"{company_data['name']}, Iloilo City",
                iloilo_street_barangay='Bonifacio Drive, Iloilo City',
                company_email=f"info@{slugify(company_data['name'])}.com",
                recruitment_email=f"hr@{slugify(company_data['name'])}.com",
                description=f"{company_data['name']} is a leading organization in Iloilo City committed to excellence and growth.",
                verification_status=Company.VERIFIED,
                verified_at=timezone.now(),
            )

            # Assign random sectors
            sectors = list(Sector.objects.order_by('?')[:random.randint(1, 3)])
            if sectors:
                company.sector_badges.set(sectors)

            # Create representative
            rep = REPRESENTATIVES[i % len(REPRESENTATIVES)]
            EmployerProfile.objects.create(
                user=user,
                company=company,
                first_name=rep['first'],
                last_name=rep['last'],
                position=rep['position'],
                phone=f'09{random.randint(100000000, 999999999)}',
                email=email,
                sex='F' if rep['first'] in ['Maria', 'Ana', 'Liza', 'Grace', 'Sheila'] else 'M',
            )

            # Create 2-3 jobs per company
            job_pool = random.sample(JOB_TEMPLATES, k=random.randint(2, 3))
            for job_data in job_pool:
                job = JobPosting.objects.create(
                    company=company,
                    title=job_data['title'],
                    description=job_data['description'],
                    location_type='iloilo',
                    street_barangay='Bonifacio Drive',
                    slots=random.randint(1, 5),
                    status='open',
                )

                # Education requirement
                if job_data.get('edu_level'):
                    JobEducationRequirement.objects.create(
                        job=job,
                        level=job_data['edu_level'],
                        course_degree=job_data.get('edu_course', ''),
                    )

                # Experience requirement
                if job_data.get('exp_years') is not None:
                    JobExperienceRequirement.objects.create(
                        job=job,
                        years_required=job_data['exp_years'],
                    )

                # Skills
                for skill_name in job_data.get('skills', []):
                    JobSkillRequirement.objects.create(
                        job=job,
                        name=skill_name,
                        is_required=True,
                    )

                # Certifications
                for cert in job_data.get('certs', []):
                    JobCertificationRequirement.objects.create(
                        job=job,
                        name=cert['name'],
                        issuing_org=cert['org'],
                        is_required=True,
                    )

            self.stdout.write(f'  ✓ {company.name} ({len(job_pool)} jobs)')

    def _seed_jobseekers(self):
        from datetime import date

        for i, js_data in enumerate(JOBSEEKERS):
            email = f"jobseeker{i+1}@seed.easyhire"

            if User.objects.filter(email=email).exists():
                self.stdout.write(f'  Skipping {email} (already exists)')
                continue

            user = User.objects.create_user(
                email=email,
                password='Seed@1234',
                user_type=User.JOBSEEKER,
                consented_to_terms=True,
                consented_at=timezone.now(),
            )

            profile = JobseekerProfile.objects.create(
                user=user,
                first_name=js_data['first'],
                last_name=js_data['last'],
                sex=js_data['sex'],
                date_of_birth=date(1995 + i % 10, (i % 12) + 1, (i % 28) + 1),
                civil_status='single',
                street_barangay='Sample Street',
                city_municipality='Iloilo City',
                province='Iloilo',
                phone=f'09{random.randint(100000000, 999999999)}',
                contact_email=email,
                profile_complete=True,
            )

            # Education
            Education.objects.create(
                profile=profile,
                level=js_data['edu_level'],
                course_degree=js_data.get('edu_course', ''),
                year_started=2015 + (i % 5),
                year_ended=2019 + (i % 5) if js_data['exp_years'] > 0 else None,
                is_current=js_data['exp_years'] == 0 and js_data['edu_level'] in ['bachelor', 'master'],
            )

            # Skills
            for skill_name in js_data.get('skills', []):
                Skill.objects.create(profile=profile, name=skill_name)

            # Certifications
            for cert in js_data.get('certs', []):
                Certification.objects.create(
                    profile=profile,
                    name=cert['name'],
                    issuing_org=cert['org'],
                    year_received=2020 + (i % 4),
                )

            # Work experience
            if js_data['exp_years'] > 0:
                WorkExperience.objects.create(
                    profile=profile,
                    position=f"Previous {js_data.get('edu_course', 'Professional')} Role",
                    description='Performed duties related to the field.',
                    month_started='6',
                    year_started=2020,
                    month_ended='5',
                    year_ended=2020 + js_data['exp_years'],
                    is_current=False,
                )

            # Sectors
            for sector_code in js_data.get('sectors', []):
                try:
                    sector = Sector.objects.get(code=sector_code)
                    profile.sectors.add(sector)
                except Sector.DoesNotExist:
                    pass

            self.stdout.write(f'  ✓ {js_data["first"]} {js_data["last"]}')
