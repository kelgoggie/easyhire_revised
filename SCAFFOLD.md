# EasyHire — Django Project Scaffold

## Project Structure

```
easyhire/                          ← project root
│
├── config/                        ← project configuration (replaces default "easyhire" config dir)
│   ├── __init__.py
│   ├── urls.py                    ← root URL dispatcher
│   ├── wsgi.py
│   ├── asgi.py                    ← needed for WebSockets (messaging)
│   └── settings/
│       ├── __init__.py
│       ├── base.py                ← shared settings
│       ├── development.py         ← local dev overrides
│       └── production.py          ← deployment settings
│
├── apps/                          ← all Django applications
│   ├── accounts/                  ← shared auth (User model, login/logout, registration base)
│   ├── jobseekers/                ← jobseeker profiles, resume, interactions
│   ├── employers/                 ← employer profiles, company info, verification
│   ├── jobs/                      ← job postings, categories, locations
│   ├── matching/                  ← compatibility algorithm, scoring engine
│   ├── messaging/                 ← match messaging (WebSocket or polling)
│   ├── analytics/                 ← public analytics dashboard data
│   └── admin_panel/               ← custom PESO admin dashboard
│
├── templates/
│   ├── base/
│   │   ├── base.html              ← root base template (head, meta, Tailwind CDN)
│   │   ├── navbar_jobseeker.html  ← jobseeker-facing navbar
│   │   ├── navbar_employer.html   ← employer-facing navbar (dark green)
│   │   └── footer.html
│   ├── public/                    ← unauthenticated pages
│   │   ├── landing_jobseeker.html
│   │   ├── landing_employer.html
│   │   ├── login_jobseeker.html
│   │   ├── login_employer.html
│   │   ├── register_step1.html    ← email + password + consent
│   │   ├── register_step2_jobseeker.html  ← personal info
│   │   ├── register_step2_employer.html   ← company rep info
│   │   ├── jobs_public.html       ← public job listings (no login)
│   │   └── analytics_public.html  ← public analytics page
│   ├── jobseekers/
│   │   ├── dashboard.html
│   │   ├── jobs_for_you.html
│   │   ├── resume.html
│   │   ├── search.html
│   │   └── company_profile.html   ← read-only view of a company
│   ├── employers/
│   │   ├── dashboard.html
│   │   ├── post_job.html
│   │   ├── my_postings.html
│   │   ├── candidates.html        ← suitable / liked / applicants tabs
│   │   ├── jobseeker_profile.html ← read-only view of a candidate
│   │   └── verification.html      ← submit docs for PESO verification
│   ├── admin_panel/
│   │   ├── dashboard.html
│   │   ├── accounts.html          ← user management
│   │   ├── verification.html      ← review & approve employer docs
│   │   ├── companies.html
│   │   ├── jobseekers.html
│   │   └── import.html            ← PESO database import tool
│   └── emails/                    ← transactional email templates
│       ├── match_notification.html
│       ├── verification_approved.html
│       └── welcome.html
│
├── static/
│   ├── css/
│   │   └── easyhire.css           ← custom CSS + Tailwind overrides
│   ├── js/
│   │   ├── resume_upload.js       ← PDF resume parsing + field autofill
│   │   ├── job_interactions.js    ← like/hide with HTMX or fetch
│   │   └── search.js              ← live search logic
│   └── images/
│       └── icons/
│
├── media/                         ← user-uploaded files (gitignored)
│   ├── resumes/                   ← uploaded PDF resumes
│   └── employer_docs/             ← verification documents
│
├── fixtures/
│   ├── iloilo_barangays.json      ← static location data for dropdowns
│   └── job_categories.json        ← seed data for job categories/sectors
│
├── requirements.txt
├── .env.example
├── manage.py
└── README.md
```

---

## App Responsibilities

### `accounts`
- Custom `User` model (email-based auth, `user_type` field: JOBSEEKER / EMPLOYER / ADMIN)
- Login, logout, password reset views
- Registration Step 1 (email + password + consent) — shared base for both user types
- Role-based redirect after login

### `jobseekers`
- `JobseekerProfile` model (personal info, address, contact)
- `Education`, `Certification`, `Skill`, `WorkExperience` models (all linked to profile)
- `SectorMembership` (junction: profile ↔ sector choices)
- Resume view + edit
- `JobInteraction` model: `(jobseeker, job, type)` where type ∈ {LIKED, HIDDEN}
- "Jobs For You" feed (calls matching engine)
- Company follow/unfollow

### `employers`
- `EmployerProfile` model (company rep personal info)
- `Company` model (name, industry, description, sector badges, verification status)
- `VerificationDocument` model (uploaded files + status)
- Job posting CRUD (with location/remote/hybrid rules)
- Candidate views (suitable, liked, applicants tabs)
- `CandidateInteraction` model: `(employer, jobseeker, job, type)` where type ∈ {LIKED}

### `jobs`
- `JobPosting` model (title, description, location, work type, requirements)
- `JobRequirement` sub-models: required education, skills, experience, certifications
- `JobCategory` and `SectorBadge` models
- Public job listing + search

### `matching`
- Scoring engine: weighted sum across education, skills, experience, certifications, sector match
- Fuzzy matching utilities (spaCy / sentence-transformers)
- `CompatibilityScore` cache model: `(jobseeker, job, score, breakdown, computed_at)`
- Score invalidation on resume update or job edit
- Match detection: when both jobseeker LIKED job AND employer LIKED jobseeker → create `Match`

### `messaging`
- `Match` model (jobseeker, employer, job, created_at)
- `Conversation` and `Message` models
- Notification triggers on new match

### `analytics`
- Aggregation queries (jobs placed, hard-to-fill, demographics)
- Public-facing dashboard views (no auth required)
- Cached computed stats (updated periodically, not on every request)

### `admin_panel`
- Custom views wrapping admin functionality (not Django's built-in admin)
- Account management (activate, deactivate, reset)
- Verification workflow (review docs → approve/reject → notify employer)
- PESO import tool: CSV/Excel upload → bulk create stub accounts with "claim" flow
- Analytics overview

---

## Key Models Overview

```
User  (accounts)
 ├── JobseekerProfile  (jobseekers)
 │    ├── Education[]
 │    ├── Certification[]
 │    ├── Skill[]
 │    ├── WorkExperience[]
 │    ├── SectorMembership[]
 │    └── JobInteraction[]       ← LIKED / HIDDEN per job
 │
 └── EmployerProfile  (employers)
      └── Company
           ├── VerificationDocument[]
           ├── JobPosting[]  (jobs)
           │    └── JobRequirement[]
           └── CandidateInteraction[]  ← LIKED per (job, jobseeker)

Match  (messaging)
 ├── Jobseeker (FK → JobseekerProfile)
 ├── Employer  (FK → Company)
 ├── Job       (FK → JobPosting)
 └── Conversation
      └── Message[]

CompatibilityScore  (matching)
 ├── Jobseeker (FK)
 ├── Job       (FK)
 ├── score     (Float 0–100)
 └── breakdown (JSONField: {skills, education, experience, certs, sector})
```

---

## URL Structure

```
/                               → public: jobseeker landing
/about/                         → public: about page
/jobs/                          → public: all job listings (no auth)
/analytics/                     → public: analytics dashboard
/login/                         → jobseeker login
/register/                      → jobseeker registration step 1
/register/info/                 → jobseeker registration step 2
/logout/                        → shared logout

/dashboard/                     → jobseeker: home dashboard
/jobs/for-you/                  → jobseeker: algorithm feed
/resume/                        → jobseeker: view/edit resume
/search/                        → jobseeker: search jobs + companies
/companies/<slug>/              → jobseeker: company profile (read-only)

/employers/                     → public: employer landing
/employers/login/               → employer login
/employers/register/            → employer registration step 1
/employers/register/info/       → employer registration step 2 (company rep)
/employers/dashboard/           → employer: home
/employers/jobs/                → employer: my job postings
/employers/jobs/new/            → employer: post a job
/employers/jobs/<id>/           → employer: job detail + candidate tabs
/employers/jobs/<id>/edit/      → employer: edit job (no title/location edit)
/employers/verification/        → employer: submit verification docs
/employers/candidates/          → employer: all candidates overview

/admin-panel/                   → PESO admin: dashboard
/admin-panel/accounts/          → PESO admin: user management
/admin-panel/verification/      → PESO admin: review employer docs
/admin-panel/import/            → PESO admin: bulk data import
/admin-panel/analytics/         → PESO admin: full analytics
```

---

## Tech Stack Summary

| Layer | Choice | Reason |
|---|---|---|
| Framework | Django 5.x | Batteries-included, great ORM |
| Database | PostgreSQL | Production-ready, JSONField support |
| Frontend | HTML + Tailwind CSS + Vanilla JS | Your existing Figma workflow |
| Interactivity | HTMX | Partial page updates without full JS framework |
| NLP/Matching | spaCy + rapidfuzz | Fuzzy skill matching, Python-native |
| PDF Parsing | pdfplumber | Resume field extraction |
| Real-time (optional) | Django Channels + Redis | For messaging/notifications |
| Deployment | Gunicorn + Nginx | Standard Django production setup |
| Auth | django-allauth (customized) | Handles email auth, password reset cleanly |

---

## Development Setup

```bash
# 1. Clone and create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
cp .env.example .env
# Edit .env with your DB credentials

# 4. Run migrations
python manage.py migrate

# 5. Load fixtures (location data, categories)
python manage.py loaddata fixtures/iloilo_barangays.json
python manage.py loaddata fixtures/job_categories.json

# 6. Create superuser (PESO admin)
python manage.py createsuperuser

# 7. Run development server
python manage.py runserver
```
