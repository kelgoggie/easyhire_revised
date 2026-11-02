"""Seed a small, DELIBERATELY DESIGNED dataset for exercising this session's
new matching-engine features:

- Per-job custom matching weights (JobMatchingWeights.use_custom_weights)
- Employer-defined "Additional Criteria" (JobCustomCriterion)
- Projects / Extracurriculars feeding into skill & experience matching
- All three skill-match tiers: literal name match, description/extra-text
  mention (Tier 2), and semantic similarity with no shared words (Tier 3)

Every jobseeker here is hand-matched against a specific job so the match
score breakdown actually demonstrates something when you open it — e.g.
Rowena Dacanay lists "Customer Service" (not "Client Relations") as a skill,
so Sunrise Call Center's "Client Relations" requirement can only be satisfied
semantically; Carlos Jalandoni never lists "React"/"Node.js" as skills at
all, only in his project description, so that's a pure Tier-2 test.

Idempotent: gated by presence of any User with `@easyhire.algo` email.
Re-run with --force to attempt again (per-row get_or_create guards still
hold).

Run from the project root:
    python manage.py seed_algorithm_demo

Password for every new account: easyhire2001
"""
import random
from datetime import date
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.employers.models import Company, EmployerProfile
from apps.jobseekers.models import (
    JobseekerProfile, Education, Skill, Certification, WorkExperience,
    Project, Extracurricular,
)
from apps.jobs.models import (
    JobPosting, JobEducationRequirement, JobSkillRequirement,
    JobCertificationRequirement, JobExperienceRequirement, JobCustomCriterion,
)
from apps.matching.models import JobMatchingWeights


PASSWORD = 'easyhire2001'
DOMAIN = 'easyhire.algo'


def _mark_email_verified(user, email):
    try:
        from allauth.account.models import EmailAddress
    except ImportError:
        return
    EmailAddress.objects.update_or_create(
        user=user, email=email, defaults={'verified': True, 'primary': True},
    )


# ── Companies + the jobs that exercise custom weights / criteria ───────────
COMPANIES = [
    {
        'slug': 'sunrise-callcenter-algo', 'name': 'Sunrise Call Center Solutions',
        'type': 'bpo', 'nature': 'IT Services / BPO',
        'address': 'Atria Park District, Mandurriao, Iloilo City',
        'rep': {'first': 'Carmela', 'last': 'Delos Santos', 'position': 'HR Manager', 'sex': 'F'},
        'jobs': [
            {
                'title': 'Customer Support Specialist', 'edu': 'senior_high', 'edu_course': '',
                'exp_months': 0, 'skills': ['Client Relations', 'Communication', 'Microsoft Office'],
                'certs': [], 'slots': 6,
                'desc': 'Handle inbound customer inquiries for a US-based telecom account via phone and chat. Training provided, shifting schedule.',
            },
            {
                'title': 'Team Lead - Customer Experience', 'edu': 'bachelor', 'edu_course': 'Business Administration',
                'exp_months': 12, 'skills': ['Client Relations', 'Team Leadership'],
                'certs': [], 'slots': 2,
                'desc': 'Lead a pod of 10-12 customer support agents, monitor QA scores, and coach for performance improvement.',
                'custom_weights': {'skills': 0.60, 'education': 0.10, 'experience': 0.25, 'certifications': 0.05},
                'custom_criteria': [
                    ('Night Shift', 'Must be amenable to a permanent night shift schedule (US business hours).', 0.15),
                    ('BPO Leadership Exp.', 'Prior experience as a team lead or shift supervisor in a BPO/call center environment.', 0.10),
                ],
            },
        ],
    },
    {
        'slug': 'panay-tech-algo', 'name': 'Panay Tech Innovations',
        'type': 'local', 'nature': 'Information Technology',
        'address': 'Iloilo Business Park, Mandurriao, Iloilo City',
        'rep': {'first': 'Patrick', 'last': 'Yulo', 'position': 'Recruitment Officer', 'sex': 'M'},
        'jobs': [
            {
                'title': 'Junior Web Developer', 'edu': 'bachelor', 'edu_course': 'Information Technology',
                'exp_months': 0, 'skills': ['React', 'Node.js', 'Git'],
                'certs': [], 'slots': 3,
                'desc': 'Build and maintain internal web tools using React on the frontend and Node.js on the backend. Entry-level, mentorship provided.',
            },
            {
                'title': 'IT Support Associate', 'edu': 'vocational', 'edu_course': 'TESDA Computer Hardware Servicing',
                'exp_months': 6, 'skills': ['Hardware Troubleshooting', 'Windows Server'],
                'certs': [], 'slots': 2,
                'desc': 'Provide first-line IT support: workstation setup, network troubleshooting, and helpdesk ticket resolution.',
                'custom_weights': {'skills': 0.50, 'education': 0.15, 'experience': 0.20, 'certifications': 0.15},
                'custom_criteria': [
                    ('On-site Mandurriao', 'Must be able to report on-site at our Iloilo Business Park office daily.', 0.10),
                ],
            },
        ],
    },
    {
        'slug': 'visayas-logistics-algo', 'name': 'Visayas Prime Logistics',
        'type': 'local', 'nature': 'Transportation & Logistics',
        'address': 'Lapuz, Iloilo City',
        'rep': {'first': 'Denise', 'last': 'Arcega', 'position': 'HR Officer', 'sex': 'F'},
        'jobs': [
            {
                'title': 'Warehouse Supervisor', 'edu': 'senior_high', 'edu_course': '',
                'exp_months': 12, 'skills': ['Inventory Optimization', 'Team Leadership'],
                'certs': [], 'slots': 2,
                'desc': 'Oversee daily warehouse operations, manage stock accuracy, and supervise a team of 5 warehouse staff.',
            },
            {
                'title': 'Logistics Coordinator', 'edu': 'bachelor', 'edu_course': '',
                'exp_months': 6, 'skills': ['Dispatch Planning', 'Communication'],
                'certs': [], 'slots': 2,
                'desc': 'Coordinate delivery schedules and routes for a fleet of 10 trucks across Iloilo and nearby provinces.',
                'custom_weights': {'skills': 0.35, 'education': 0.20, 'experience': 0.35, 'certifications': 0.10},
                'custom_criteria': [
                    ('Port Travel', 'Willing to travel periodically to Iloilo ports and inter-island terminals for coordination.', 0.15),
                ],
            },
        ],
    },
    {
        'slug': 'iloilo-wellness-algo', 'name': 'Iloilo Wellness Clinic',
        'type': 'local', 'nature': 'Healthcare / Hospital',
        'address': 'Jaro, Iloilo City',
        'rep': {'first': 'Mark', 'last': 'Villareal', 'position': 'Talent Acquisition', 'sex': 'M'},
        'jobs': [
            {
                'title': 'Medical Receptionist', 'edu': 'senior_high', 'edu_course': '',
                'exp_months': 0, 'skills': ['Front Desk Operations', 'Data Entry'],
                'certs': [], 'slots': 2,
                'desc': 'Greet patients, manage appointment scheduling, and maintain accurate patient records at the front desk.',
            },
            {
                'title': 'Community Health Aide', 'edu': 'vocational', 'edu_course': '',
                'exp_months': 0, 'skills': ['Patient Care', 'Communication'],
                'certs': [('First Aid Certification', 'Red Cross')], 'slots': 3,
                'desc': 'Support community health outreach programs, basic first aid stations, and health education drives.',
                'custom_weights': {'skills': 0.45, 'education': 0.25, 'experience': 0.15, 'certifications': 0.15},
                'custom_criteria': [
                    ('Community Outreach Exp.', 'Experience volunteering or working in community health outreach programs.', 0.20),
                ],
            },
        ],
    },
]


# ── Jobseekers, each hand-matched against one job above ────────────────────
JOBSEEKERS = [
    {
        'first': 'Rowena', 'last': 'Dacanay', 'sex': 'F', 'age': 24, 'barangay': 'Jaro',
        'edu': ('senior_high', 'TVL — Information & Communication Technology', 'Iloilo National High School'),
        'skills': ['Customer Service', 'Communication', 'Microsoft Office'],
        'experience': [('Customer Service Representative', 'Convergys Philippines', 1)],
        'certs': [],
        'projects': [
            ('Front Desk Revamp',
             'Helped redesign the client intake process at a school organization to improve how students were greeted and assisted.'),
        ],
        'extracurriculars': [
            ('Student Council', 'Public Relations Officer',
             'Handled inquiries from fellow students and coordinated communication between the student body and faculty.'),
        ],
    },
    {
        'first': 'Miguel', 'last': 'Tajonera', 'sex': 'M', 'age': 29, 'barangay': 'Mandurriao',
        'edu': ('bachelor', 'BS Business Administration', 'University of San Agustin'),
        'skills': ['Customer Service', 'Team Leadership', 'Communication'],
        'experience': [
            ('Customer Service Representative', 'Teleperformance', 3),
            ('Shift Supervisor', 'Concentrix', 2),
        ],
        'certs': [],
        'projects': [],
        'extracurriculars': [
            ('BPO Night Shift Crew Association', 'Member',
             'Participated in a peer support group for agents working permanent night shift schedules handling US accounts.'),
        ],
    },
    {
        'first': 'Carlos', 'last': 'Jalandoni', 'sex': 'M', 'age': 23, 'barangay': 'La Paz',
        'edu': ('bachelor', 'BS Computer Science', 'Central Philippine University'),
        'skills': ['Python', 'JavaScript', 'SQL'],
        'experience': [],
        'certs': [],
        'projects': [
            ('Inventory Tracker App',
             'Built a full-stack web app using React for the frontend and Node.js/Express for the backend API, with a SQL database.'),
        ],
        'extracurriculars': [
            ('Coding Club', 'Member', 'Collaborated with classmates on small Git-based group projects.'),
        ],
    },
    {
        'first': 'Ana Belen', 'last': 'Suyat', 'sex': 'F', 'age': 26, 'barangay': 'Molo',
        'edu': ('vocational', 'TESDA Computer Hardware Servicing', 'Iloilo TESDA Training Center'),
        'skills': ['Basic Networking', 'Windows Server', 'Active Directory'],
        'experience': [('IT Helpdesk Intern', 'Iloilo Science and Technology University', 1)],
        'certs': [],
        'projects': [
            ('Home Lab Server Setup',
             'Set up a home lab running Windows Server, configured Active Directory, and practiced basic hardware troubleshooting for a CompTIA A+ prep course.'),
        ],
        'extracurriculars': [],
    },
    {
        'first': 'Rafael', 'last': 'Montelibano', 'sex': 'M', 'age': 34, 'barangay': 'Lapuz Norte',
        'edu': ('senior_high', 'TVL — Information & Communication Technology', 'Iloilo National High School'),
        'skills': ['Inventory Management', 'Physical Stamina', 'Team Leadership'],
        'experience': [('Warehouse Staff', 'Megaworld Logistics', 3)],
        'certs': [],
        'projects': [
            ('Warehouse Layout Optimization',
             'Proposed and helped implement a new shelf layout during an OJT that optimized inventory flow and reduced picking time by 15%.'),
        ],
        'extracurriculars': [],
    },
    {
        'first': 'Grace', 'last': 'Impas', 'sex': 'F', 'age': 31, 'barangay': 'San Pedro',
        'edu': ('bachelor', 'BS Business Administration', 'University of the Philippines Visayas'),
        'skills': ['Communication', 'Scheduling', 'Microsoft Excel'],
        'experience': [('Administrative Assistant', 'Iloilo Provincial Capitol', 2)],
        'certs': [],
        'projects': [],
        'extracurriculars': [
            ('Inter-island Trade Fair Volunteer Group', 'Logistics Volunteer',
             'Coordinated delivery schedules and dispatch planning for vendor booths across multiple port terminals during an annual trade fair.'),
        ],
    },
    {
        'first': 'Teresa', 'last': 'Nava', 'sex': 'F', 'age': 22, 'barangay': 'Bolilao',
        'edu': ('senior_high', 'ABM Strand', 'Iloilo Central Commercial High School'),
        'skills': ['Customer Service', 'Data Entry', 'Scheduling'],
        'experience': [],
        'certs': [],
        'projects': [],
        'extracurriculars': [
            ('Campus Clinic Volunteer', 'Front Desk Volunteer',
             'Greeted patients, scheduled appointments, and managed basic data entry at the campus health clinic front desk.'),
        ],
    },
    {
        'first': 'Joel', 'last': 'Bacolod', 'sex': 'M', 'age': 27, 'barangay': 'Calumpang',
        'edu': ('vocational', 'TESDA Caregiving NC II', 'Iloilo TESDA Training Center'),
        'skills': ['Patient Care', 'Communication', 'First Aid'],
        'experience': [('Nurse Aide', 'Iloilo Doctors Hospital', 1)],
        'certs': [('First Aid Certification', 'Red Cross')],
        'projects': [],
        'extracurriculars': [
            ('Red Cross Youth Volunteer', 'Volunteer',
             'Assisted in community blood donation drives, basic first aid demonstrations, and health education outreach programs in local barangays.'),
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed a small hand-matched dataset for testing custom matching weights, additional criteria, and project/extracurricular matching.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
            help='Run even if the seed marker (@easyhire.algo users) already exists.')

    def handle(self, *args, **opts):
        random.seed(42)

        marker_exists = User.objects.filter(email__endswith=f'@{DOMAIN}').exists()
        if marker_exists and not opts['force']:
            self.stdout.write(self.style.WARNING(
                f'Algorithm-demo seed already applied (@{DOMAIN} users exist). '
                f'Re-run with --force to attempt again — per-row guards still hold.'
            ))
            return

        # ── Companies, reps, jobs (with custom weights / criteria) ────────
        job_count = 0
        custom_weight_job_count = 0
        custom_criteria_count = 0

        for cd in COMPANIES:
            email = f"{cd['slug']}@{DOMAIN}"
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    'user_type': User.EMPLOYER, 'is_active': True,
                    'consented_to_terms': True, 'consented_at': timezone.now(),
                },
            )
            user.set_password(PASSWORD)
            user.user_type = User.EMPLOYER
            user.save()
            _mark_email_verified(user, email)

            company, _ = Company.objects.get_or_create(
                slug=cd['slug'],
                defaults={
                    'name': cd['name'], 'type_of_company': cd['type'],
                    'nature_of_company': cd['nature'], 'company_email': email,
                    'recruitment_email': email, 'main_branch_address': cd['address'],
                    'verification_status': Company.VERIFIED, 'verified_at': timezone.now(),
                },
            )

            rep = cd['rep']
            EmployerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'company': company, 'first_name': rep['first'], 'last_name': rep['last'],
                    'sex': rep['sex'], 'position': rep['position'],
                    'phone': f"0917{random.randint(1000000, 9999999)}", 'email': email,
                },
            )

            for jt in cd['jobs']:
                job, created = JobPosting.objects.get_or_create(
                    company=company, title=jt['title'],
                    defaults={
                        'description': jt['desc'], 'location_type': JobPosting.ILOILO,
                        'barangay_name': cd['address'].split(',')[0].strip(), 'city': 'Iloilo City',
                        'slots': jt['slots'], 'status': JobPosting.STATUS_OPEN,
                        'contact_email': company.recruitment_email,
                    },
                )
                if created:
                    JobEducationRequirement.objects.create(
                        job=job, level=jt['edu'], course_degree=jt['edu_course'],
                    )
                    JobExperienceRequirement.objects.create(
                        job=job, months_required=jt['exp_months'], any_experience_accepted=True,
                    )
                    for s in jt['skills']:
                        JobSkillRequirement.objects.create(job=job, name=s, is_required=True)
                    for cname, corg in jt['certs']:
                        JobCertificationRequirement.objects.create(
                            job=job, name=cname, issuing_org=corg, is_required=True,
                        )
                    if 'custom_weights' in jt:
                        w = jt['custom_weights']
                        JobMatchingWeights.objects.create(
                            job=job, use_custom_weights=True,
                            weight_skills=w['skills'], weight_education=w['education'],
                            weight_experience=w['experience'], weight_certifications=w['certifications'],
                        )
                        custom_weight_job_count += 1
                    for i, (cname, ctext, cweight) in enumerate(jt.get('custom_criteria', [])):
                        JobCustomCriterion.objects.create(
                            job=job, name=cname, requirement_text=ctext, weight=cweight, order=i,
                        )
                        custom_criteria_count += 1
                    job_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Jobs ready: {job_count} ({custom_weight_job_count} with custom weights, '
            f'{custom_criteria_count} additional criteria rows across them)'
        ))

        # ── Jobseekers, hand-matched against the jobs above ───────────────
        today = date.today()
        seeker_count = 0
        project_count = 0
        extracurricular_count = 0

        for jd in JOBSEEKERS:
            email = f"{jd['first'].lower().replace(' ', '')}.{jd['last'].lower().replace(' ', '')}@{DOMAIN}"
            user, _ = User.objects.get_or_create(
                email=email,
                defaults={
                    'user_type': User.JOBSEEKER, 'is_active': True,
                    'consented_to_terms': True, 'consented_at': timezone.now(),
                },
            )
            user.set_password(PASSWORD)
            user.user_type = User.JOBSEEKER
            user.save()
            _mark_email_verified(user, email)

            dob = date(today.year - jd['age'], random.randint(1, 12), random.randint(1, 28))
            profile, created = JobseekerProfile.objects.get_or_create(
                user=user,
                defaults={
                    'first_name': jd['first'], 'last_name': jd['last'], 'sex': jd['sex'],
                    'date_of_birth': dob,
                    'civil_status': 'single',
                    'street_barangay': f"{random.randint(10, 999)} {random.choice(['Iznart', 'Rizal', 'Luna', 'Bonifacio'])} Street",
                    'barangay': jd['barangay'], 'city_municipality': 'Iloilo City',
                    'province': 'Iloilo', 'province_code': '063000000',
                    'phone': f"0917{random.randint(1000000, 9999999)}", 'contact_email': email,
                    'profile_complete': True, 'profile_visibility': 'public',
                    'sector_badge_visibility': 'public',
                    'bio': f"Looking for opportunities in Iloilo City that match my background in {jd['skills'][0].lower()}.",
                },
            )

            if created:
                level, course, inst = jd['edu']
                Education.objects.create(
                    profile=profile, level=level, course_degree=course, institution=inst,
                    year_started=today.year - jd['age'] + 18,
                    year_ended=today.year - jd['age'] + 22,
                )
                for s in jd['skills']:
                    Skill.objects.create(profile=profile, name=s)
                for position, company_name, years in jd['experience']:
                    yr_start = today.year - years
                    WorkExperience.objects.create(
                        profile=profile, position=position, company=company_name,
                        month_started='January', year_started=yr_start,
                        month_ended='December', year_ended=today.year,
                        description=f"Worked as {position} at {company_name}.",
                    )
                for cname, corg in jd['certs']:
                    Certification.objects.create(
                        profile=profile, name=cname, issuing_org=corg,
                        year_received=today.year - 1,
                    )
                for title, description in jd['projects']:
                    Project.objects.create(
                        profile=profile, title=title, description=description,
                        year_started=today.year - 1, year_ended=today.year,
                    )
                    project_count += 1
                for name, role, description in jd['extracurriculars']:
                    Extracurricular.objects.create(
                        profile=profile, name=name, role=role, description=description,
                        year_started=today.year - 2, year_ended=today.year - 1,
                    )
                    extracurricular_count += 1
                seeker_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'Jobseekers ready: {seeker_count} ({project_count} projects, '
            f'{extracurricular_count} extracurriculars)'
        ))

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Log in as any @{DOMAIN} account with password: {PASSWORD}\n'
            f'Try: carlos.jalandoni@{DOMAIN} against "Junior Web Developer" (Panay Tech Innovations) '
            f'— React/Node.js only show up in his project description, a pure Tier-2 match.\n'
            f'Or: miguel.tajonera@{DOMAIN} against "Team Lead - Customer Experience" (Sunrise Call '
            f'Center Solutions) — custom weights + two Additional Criteria, one of which his work '
            f'history and extracurricular literally satisfy.'
        ))
