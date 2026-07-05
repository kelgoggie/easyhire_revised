"""Starter vocabulary of skills the resume parser should recognise.

Merged into the ``known_skills`` list handed to
:func:`apps.jobseekers.resume_parser.parse_resume` so day-1 uploads catch
common PH job skills even if no other jobseeker has typed them yet.
User-typed Skill rows continue to expand the effective vocab over time
via the DB half of the merge in ``parse_resume_pdf``.

Guidelines for editing:
  - Whole-word, case-insensitive matching. "Excel" catches "MS Excel"
    and "Microsoft Excel" only if those exact substrings are present.
  - Prefer the canonical name — "Microsoft Excel", not "MS Excel" —
    since that's what shows up on the jobseeker's resume row after parsing.
  - Add variants generously; the parser dedupes case-insensitively.
"""

COMMON_SKILLS = [
    # ── Soft / interpersonal ──────────────────────────────────────
    'Communication', 'Teamwork', 'Leadership', 'Problem Solving',
    'Time Management', 'Adaptability', 'Critical Thinking',
    'Public Speaking', 'Presentation', 'Negotiation', 'Conflict Resolution',
    'Attention to Detail', 'Organization', 'Multitasking',
    'Interpersonal Skills', 'Customer Service', 'Active Listening',
    'Decision Making', 'Creativity', 'Work Ethic', 'Dependability',
    'Punctuality', 'Emotional Intelligence', 'Collaboration',
    'Cross-cultural Communication', 'Mentoring', 'Coaching',

    # ── Language / literacy ───────────────────────────────────────
    'English Proficiency', 'Filipino Proficiency', 'Hiligaynon',
    'Business Writing', 'Report Writing', 'Technical Writing',
    'Copywriting', 'Editing', 'Proofreading', 'Translation',

    # ── Office / productivity software ────────────────────────────
    'Microsoft Office', 'Microsoft Word', 'Microsoft Excel',
    'Microsoft PowerPoint', 'Microsoft Outlook', 'Microsoft Teams',
    'Google Workspace', 'Google Docs', 'Google Sheets', 'Google Slides',
    'Google Drive', 'Gmail', 'Google Calendar', 'Zoom', 'Slack',
    'Trello', 'Notion', 'Asana', 'Basecamp', 'ClickUp',

    # ── Design / creative tools ───────────────────────────────────
    'Adobe Photoshop', 'Adobe Illustrator', 'Adobe InDesign',
    'Adobe Premiere Pro', 'Adobe After Effects', 'Canva', 'Figma',
    'Sketch', 'AutoCAD', 'SketchUp', 'CorelDRAW', 'Lightroom',
    'Graphic Design', 'Video Editing', 'Photography', 'Logo Design',

    # ── Professional services ─────────────────────────────────────
    'Accounting', 'Bookkeeping', 'Auditing', 'Financial Reporting',
    'Financial Analysis', 'Tax Preparation', 'Budgeting', 'Payroll',
    'Cost Accounting', 'QuickBooks', 'SAP', 'Xero',
    'Human Resources', 'HR Management', 'Recruitment', 'Talent Acquisition',
    'Employee Relations', 'Training and Development', 'Compensation and Benefits',
    'Marketing', 'Digital Marketing', 'Social Media Marketing',
    'Content Marketing', 'SEO', 'SEM', 'Email Marketing', 'Copywriting',
    'Brand Management', 'Market Research',
    'Sales', 'Business Development', 'Account Management',
    'Client Relationship', 'Lead Generation', 'Cold Calling',
    'CRM', 'Salesforce', 'HubSpot',
    'Project Management', 'Agile', 'Scrum', 'Kanban', 'PMP',
    'Risk Management', 'Change Management', 'Process Improvement',

    # ── Customer service / retail / hospitality ───────────────────
    'POS Systems', 'Cash Handling', 'Cashiering', 'Inventory Management',
    'Merchandising', 'Retail Sales', 'Waitering', 'Bartending',
    'Housekeeping', 'Cleaning', 'Front Desk', 'Reception',
    'Concierge', 'Guest Services', 'Food Preparation', 'Cooking',
    'Baking', 'Pastry', 'Barista', 'Food Safety', 'ServSafe',
    'Tourism', 'Event Coordination', 'Event Planning',

    # ── Healthcare / caregiving ───────────────────────────────────
    'Patient Care', 'Nursing', 'Vital Signs', 'IV Insertion',
    'CPR', 'First Aid', 'BLS', 'ACLS', 'Medical Documentation',
    'Medication Administration', 'Wound Care', 'Bedside Manner',
    'Elderly Care', 'Caregiving', 'Physical Therapy', 'Occupational Therapy',
    'Phlebotomy', 'Radiography', 'Pharmacy Assistance',
    'Medical Terminology', 'HIPAA',

    # ── Education / training ──────────────────────────────────────
    'Lesson Planning', 'Classroom Management', 'Curriculum Development',
    'Tutoring', 'Special Education', 'Early Childhood Education',
    'Instructional Design', 'Educational Technology', 'Student Assessment',

    # ── Trades / manual / technical ───────────────────────────────
    'Welding', 'Carpentry', 'Plumbing', 'Masonry', 'Painting',
    'Electrical Wiring', 'Electrical Installation', 'HVAC',
    'Automotive Repair', 'Motorcycle Repair', 'Engine Repair',
    'Blueprint Reading', 'Machining', 'CNC', 'Forklift Operation',
    'Heavy Equipment Operation', 'Driving', 'Delivery',
    'Warehouse Operations', 'Logistics', 'Supply Chain',
    'Quality Control', 'Physical Stamina', 'Manual Labor',
    'Landscaping', 'Farming', 'Fisheries', 'Aquaculture',

    # ── Programming / IT / data ───────────────────────────────────
    'Python', 'Java', 'JavaScript', 'TypeScript', 'C#', 'C++',
    'PHP', 'Ruby', 'Go', 'Rust', 'Swift', 'Kotlin', 'Dart',
    'HTML', 'CSS', 'HTML/CSS', 'React', 'React.js', 'Vue', 'Vue.js',
    'Angular', 'Node.js', 'Next.js', 'Django', 'Flask', 'Laravel',
    'Spring Boot', '.NET', 'Ruby on Rails', 'Tailwind CSS', 'Bootstrap',
    'SQL', 'MySQL', 'PostgreSQL', 'MongoDB', 'SQLite', 'Redis',
    'Firebase', 'AWS', 'Azure', 'Google Cloud', 'Docker', 'Kubernetes',
    'Git', 'GitHub', 'GitLab', 'CI/CD', 'REST APIs', 'GraphQL',
    'Linux', 'Bash', 'Networking', 'Cybersecurity', 'Penetration Testing',
    'Data Analysis', 'Data Visualization', 'Power BI', 'Tableau',
    'Excel Macros', 'VBA', 'Machine Learning', 'Deep Learning',
    'TensorFlow', 'PyTorch', 'Pandas', 'NumPy', 'Scikit-learn',
    'Statistics', 'R', 'Web Scraping',

    # ── Admin / clerical ──────────────────────────────────────────
    'Data Entry', 'Filing', 'Scheduling', 'Calendar Management',
    'Travel Coordination', 'Meeting Coordination', 'Records Management',
    'Transcription', 'Minute-Taking', 'Correspondence',
    'Document Preparation', 'Executive Assistance',

    # ── Safety / compliance ───────────────────────────────────────
    'Occupational Safety', 'OSHA', 'DOLE Compliance',
    'Emergency Response', 'Fire Safety', 'Security Operations',
    'Surveillance', 'Investigation', 'Report Writing',

    # ── Language teaching / BPO ───────────────────────────────────
    'ESL Teaching', 'Call Center Operations', 'Technical Support',
    'Chat Support', 'Email Support', 'Escalation Handling',
    'Ticketing Systems', 'Zendesk', 'Freshdesk',
    'Troubleshooting', 'Root Cause Analysis',
]
