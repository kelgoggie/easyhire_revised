from django.shortcuts import render
import json


def get_analytics_context(request):
    from django.utils import timezone
    from datetime import timedelta, date
    from django.db.models import Count
    from django.db.models.functions import TruncMonth
    from apps.jobseekers.models import JobseekerProfile, WorkExperience, Education, Skill, JobInteraction, Sector
    from apps.jobs.models import JobPosting, Application
    from apps.employers.models import Company, EmployerProfile
    from collections import Counter

    # ── Applicant stats ────────────────────────────────────────────
    total_applicants = JobseekerProfile.objects.count()
    men = JobseekerProfile.objects.filter(sex='M').count()
    women = JobseekerProfile.objects.filter(sex='F').count()

    civil_status_data = JobseekerProfile.objects.values(
        'civil_status'
    ).annotate(count=Count('id')).order_by('-count')

    civil_status_labels = {
        'single': 'Single', 'married': 'Married', 'widowed': 'Widowed',
        'separated': 'Separated', 'annulled': 'Annulled', '': 'Not specified',
    }
    civil_status = [
        {
            'label': civil_status_labels.get(row['civil_status'], row['civil_status']),
            'count': row['count'],
            'pct': round(row['count'] / total_applicants * 100) if total_applicants else 0,
        }
        for row in civil_status_data
    ]

    with_experience = WorkExperience.objects.values('profile').distinct().count()
    without_experience = total_applicants - with_experience

    LEVEL_LABELS = {
        'elementary': 'Elementary',
        'junior_high': 'High School / Junior High',
        'senior_high': 'Senior High School',
        'vocational': 'Vocational / TESDA',
        'associate': 'Associate Degree',
        'bachelor': "Bachelor's Degree",
        'master': "Master's Degree",
        'doctorate': 'Doctorate',
    }
    # Highest educational attainment per jobseeker — each jobseeker is
    # bucketed once at the highest level they've recorded. Earlier
    # implementation counted every Education row (so a jobseeker with
    # elementary → bachelor showed up in every level's bar). Counts here
    # now sum to ≤ total_applicants (jobseekers with no education entries
    # aren't represented in any bucket).
    LEVEL_ORDER = ['elementary', 'junior_high', 'senior_high', 'vocational',
                   'associate', 'bachelor', 'master', 'doctorate']
    highest_per_profile = {}
    for profile_id, level in Education.objects.values_list('profile_id', 'level'):
        if level not in LEVEL_ORDER:
            continue
        idx = LEVEL_ORDER.index(level)
        if idx > highest_per_profile.get(profile_id, -1):
            highest_per_profile[profile_id] = idx

    level_counts = Counter(LEVEL_ORDER[idx] for idx in highest_per_profile.values())
    education_breakdown = [
        {
            'label': LEVEL_LABELS[level],
            'count': level_counts[level],
            'pct': round(level_counts[level] / total_applicants * 100) if total_applicants else 0,
        }
        for level in LEVEL_ORDER
        if level_counts.get(level, 0) > 0
    ]
    # Show the most attained level at the top — same visual order as before.
    education_breakdown.sort(key=lambda x: -x['count'])

    # ── Monthly stats ──────────────────────────────────────────────
    now = timezone.now()
    twelve_months_ago = now - timedelta(days=365)

    # Year filter (from ?year=YYYY), defaults to current year
    try:
        selected_year = int(request.GET.get('year', now.year))
    except (TypeError, ValueError):
        selected_year = now.year

    def monthly_counts_for_year(qs, year):
        """Returns [count_jan, count_feb, ..., count_dec] for the given year."""
        rows = (qs.filter(created_at__year=year)
                  .annotate(month=TruncMonth('created_at'))
                  .values('month')
                  .annotate(count=Count('id'))
                  .order_by('month'))
        by_month = {r['month'].month: r['count'] for r in rows}
        return [by_month.get(m, 0) for m in range(1, 13)]

    # Per-month series for the selected year (12 buckets, padded with zeros)
    new_jobseekers_monthly = monthly_counts_for_year(JobseekerProfile.objects, selected_year)
    new_employers_monthly  = monthly_counts_for_year(EmployerProfile.objects, selected_year)
    applications_monthly   = monthly_counts_for_year(Application.objects, selected_year)
    placements_monthly     = monthly_counts_for_year(
        Application.objects.filter(status='accepted'), selected_year
    )
    # Comparison-chart series: actual hires (terminal 'hired' state, not
    # 'accepted' which is still mid-flow) and new job postings per month.
    hired_monthly = monthly_counts_for_year(
        Application.objects.filter(status='hired'), selected_year
    )
    new_jobs_monthly = monthly_counts_for_year(
        JobPosting.objects.filter(deleted_at__isnull=True), selected_year
    )

    # Totals for the chart footers
    jobseekers_this_year = sum(new_jobseekers_monthly)
    employers_this_year  = sum(new_employers_monthly)
    applications_this_year = sum(applications_monthly)
    placements_this_year   = sum(placements_monthly)
    hired_this_year        = sum(hired_monthly)
    new_jobs_this_year     = sum(new_jobs_monthly)

    jobseekers_all_time  = JobseekerProfile.objects.count()
    employers_all_time   = EmployerProfile.objects.count()
    applications_all_time = Application.objects.count()
    placements_all_time   = Application.objects.filter(status='accepted').count()
    hired_all_time        = Application.objects.filter(status='hired').count()

    # External-hire totals + per-month series for the EasyHire-vs-External
    # comparison line. The field is a running counter with no per-hire
    # timestamp, so we attribute each job's external-hire count to the
    # month the job was posted — a defensible approximation for the trend
    # line (a job's hires generally happen in the same month or the month
    # after posting). Not exact if an employer records external hires
    # months later, but close enough for the shape of the curve.
    from django.db.models import Sum
    external_hires_this_year = (
        JobPosting.objects
        .filter(created_at__year=selected_year)
        .aggregate(total=Sum('externally_hired_count'))['total']
    ) or 0
    external_hires_all_time = (
        JobPosting.objects.aggregate(total=Sum('externally_hired_count'))['total']
    ) or 0

    def external_hires_monthly_for_year(year):
        rows = (JobPosting.objects
                .filter(created_at__year=year)
                .annotate(month=TruncMonth('created_at'))
                .values('month')
                .annotate(total=Sum('externally_hired_count'))
                .order_by('month'))
        by_month = {r['month'].month: (r['total'] or 0) for r in rows}
        return [by_month.get(m, 0) for m in range(1, 13)]

    external_hires_monthly = external_hires_monthly_for_year(selected_year)

    # Years that actually have data (for the dropdown)
    js_year_rows = JobseekerProfile.objects.dates('created_at', 'year', order='DESC')
    available_years = sorted({d.year for d in js_year_rows} | {now.year}, reverse=True)

    # Old shape (kept for backward-compatible templates / summary cards)
    new_applicants_per_month = list(
        JobseekerProfile.objects.filter(
            created_at__gte=twelve_months_ago
        ).annotate(month=TruncMonth('created_at')).values('month').annotate(
            count=Count('id')
        ).order_by('month')
    )

    interactions_per_month = list(
        JobInteraction.objects.filter(
            created_at__gte=twelve_months_ago
        ).annotate(month=TruncMonth('created_at')).values('month').annotate(
            count=Count('id')
        ).order_by('month')
    )

    total_interactions = JobInteraction.objects.count()
    avg_interactions = round(total_interactions / total_applicants, 1) if total_applicants else 0

    # ── Job stats ──────────────────────────────────────────────────
    all_jobs = JobPosting.objects.filter(status='open', deleted_at__isnull=True)
    total_jobs = all_jobs.count()
    local_jobs = all_jobs.filter(location_type='iloilo').count()
    overseas_jobs = all_jobs.filter(location_type='overseas').count()
    remote_jobs = all_jobs.filter(location_type='remote').count()

    # Aggregate open jobs by normalized title (case-insensitive, whitespace
    # stripped) so multiple postings of "Bank Teller" across BDO, Metrobank,
    # etc. collapse into one row. Titles are the labor-market signal — an
    # employer analyst cares "which ROLES take longest to fill", not which
    # specific posts. Company identity is intentionally dropped.
    hard_to_fill = [job for job in all_jobs.select_related('company') if job.is_hard_to_fill]
    hard_to_fill_count = len(hard_to_fill)

    from django.utils import timezone as _tz
    in_demand_open = list(
        JobPosting.objects.filter(status='open', deleted_at__isnull=True)
        .annotate(interaction_count=Count('jobseeker_interactions'))
    )

    def _norm_title(title):
        return ' '.join((title or '').strip().split()).lower()

    # In Demand: aggregate by title, sum interactions, avg per post. Rank
    # by total interactions descending. Top 10 titles only.
    demand_groups = {}
    for j in in_demand_open:
        key = _norm_title(j.title)
        if not key or not j.interaction_count:
            continue
        g = demand_groups.setdefault(key, {
            'display': j.title.strip(), 'total_interactions': 0, 'post_count': 0,
        })
        g['total_interactions'] += j.interaction_count
        g['post_count'] += 1
    in_demand_top = sorted(
        demand_groups.values(), key=lambda g: g['total_interactions'], reverse=True,
    )[:10]
    for g in in_demand_top:
        g['avg_interactions'] = round(g['total_interactions'] / g['post_count'], 1) if g['post_count'] else 0
    in_demand_chart = [
        {'label': g['display'], 'count': g['total_interactions']}
        for g in in_demand_top
    ]

    # Hard to Fill: aggregate hard-to-fill posts by title. Rank by average
    # days open (a title that stays open longer on average is a stronger
    # skills-gap signal than one with lots of posts). Top 10 titles only.
    hard_groups = {}
    now = _tz.now()
    for j in hard_to_fill:
        key = _norm_title(j.title)
        if not key:
            continue
        days_open = max((now - j.created_at).days, 1)
        g = hard_groups.setdefault(key, {
            'display': j.title.strip(), 'post_count': 0, 'total_days': 0,
        })
        g['post_count'] += 1
        g['total_days'] += days_open
    for g in hard_groups.values():
        g['avg_days'] = round(g['total_days'] / g['post_count'], 1) if g['post_count'] else 0
    hard_to_fill_top = sorted(
        hard_groups.values(), key=lambda g: g['avg_days'], reverse=True,
    )[:10]
    hard_to_fill_chart = [
        {'label': g['display'], 'count': g['avg_days']}
        for g in hard_to_fill_top
    ]

    # Applicant Insights
    sector_data = Sector.objects.annotate(
        count=Count('jobseekers')
    ).order_by('-count')

    # Preferred jobs — stored on each JobseekerProfile as a comma-separated
    # string ("Computer Science, Education, Information Technology"). The
    # resume UI treats each entry as a chip, so the analytics aggregation
    # has to mirror that: split on comma, count each individual title
    # instead of treating the whole comma-joined string as one label.
    queries = JobseekerProfile.objects.exclude(
        job_search_query=''
    ).values_list('job_search_query', flat=True)
    query_counter = Counter()
    for raw in queries:
        for piece in (raw or '').split(','):
            title = piece.strip().lower()
            if title:
                query_counter[title] += 1
    jobs_of_interest = [
        {'query': q, 'count': c}
        for q, c in query_counter.most_common(10)
    ]

    common_skills = list(
        Skill.objects.values('name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
    )

    # Jobseeker locations — aggregated to Iloilo City DISTRICT (7 buckets)
    # instead of the ~180-barangay long tail. See apps/analytics/iloilo_districts
    # for the mapping and its ambiguity notes.
    from apps.analytics.iloilo_districts import resolve_district, DISTRICTS
    _district_counter = Counter()
    for row in JobseekerProfile.objects.exclude(barangay='').values('barangay'):
        _district_counter[resolve_district(row['barangay'])] += 1
    # Preserve the canonical district order in the chart, drop empty buckets,
    # then append 'Other' last when present so unmapped rows are visible but
    # never lead the list.
    barangay_data = [
        {'barangay': d, 'count': _district_counter[d]}
        for d in DISTRICTS if _district_counter[d]
    ]
    if _district_counter.get('Other'):
        barangay_data.append({'barangay': 'Other', 'count': _district_counter['Other']})

    # ── Age groups ────────────────────────────────────────────────
    today = date.today()
    age_buckets = {'<18': 0, '18-24': 0, '25-34': 0, '35-44': 0, '45-54': 0, '55-64': 0, '65+': 0}
    for dob in JobseekerProfile.objects.exclude(date_of_birth__isnull=True).values_list('date_of_birth', flat=True):
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18:        age_buckets['<18'] += 1
        elif age < 25:      age_buckets['18-24'] += 1
        elif age < 35:      age_buckets['25-34'] += 1
        elif age < 45:      age_buckets['35-44'] += 1
        elif age < 55:      age_buckets['45-54'] += 1
        elif age < 65:      age_buckets['55-64'] += 1
        else:               age_buckets['65+'] += 1
    age_groups = [{'label': k, 'count': v} for k, v in age_buckets.items()]

    # ── Employer demographics ─────────────────────────────────────
    total_companies = Company.objects.count()
    total_employers = EmployerProfile.objects.count()

    company_type_labels = dict(Company._meta.get_field('type_of_company').choices)
    company_types = [
        {'label': company_type_labels.get(row['type_of_company'], row['type_of_company'] or 'Unspecified'),
         'count': row['count']}
        for row in Company.objects.values('type_of_company').annotate(count=Count('id')).order_by('-count')
    ]

    # Nature of Company — group semantically into canonical industry buckets
    # so "Hospital", "Medical Clinic", "Healthcare Center" all roll up as Healthcare.
    #
    # Performance: the NLP model is ~80MB and takes 5–50s to load on first use.
    # We:
    #   1. Cache the clustering result per-(set of natures) for 1 hour, so
    #      repeat page loads are instant.
    #   2. Skip the model entirely if there are 0–2 unique natures (nothing
    #      meaningful to cluster), so a fresh DB shows no NLP delay at all.
    #   3. Only run NLP if the model has already been loaded into memory —
    #      otherwise fall back to raw nature labels. Run `python manage.py
    #      warm_nlp` once after server start to enable the smart grouping.
    raw_natures = list(
        Company.objects.exclude(nature_of_company='').values_list('nature_of_company', flat=True)
    )

    industry_counter = Counter()
    unique_natures = set(raw_natures)

    nature_to_industry = None
    if len(unique_natures) >= 3:
        from django.core.cache import cache
        cache_key = 'analytics:nature_clusters:' + str(hash(frozenset(unique_natures)))
        nature_to_industry = cache.get(cache_key)
        if nature_to_industry is None:
            from apps.jobseekers import nlp_service
            # Only attempt clustering if the model is already loaded in memory
            # (so we don't block this request on the first-time download).
            if nlp_service._model is not None:
                nature_to_industry = nlp_service.cluster_to_canonical(unique_natures)
                cache.set(cache_key, nature_to_industry, 60 * 60)  # 1 hour

    for nature in raw_natures:
        if nature_to_industry:
            bucket = nature_to_industry.get(nature, nature) or 'Unspecified'
        else:
            bucket = nature or 'Unspecified'
        industry_counter[bucket] += 1

    company_natures = [
        {'label': label, 'count': count}
        for label, count in industry_counter.most_common(12)
    ]

    # Company locations rolled up to Iloilo City DISTRICT (same reason as
    # jobseeker locations above — 7 clean buckets beats a 30-entry long tail).
    _co_district_counter = Counter()
    for row in Company.objects.exclude(iloilo_barangay_name='').values('iloilo_barangay_name'):
        _co_district_counter[resolve_district(row['iloilo_barangay_name'])] += 1
    company_locations = [
        {'label': d, 'count': _co_district_counter[d]}
        for d in DISTRICTS if _co_district_counter[d]
    ]
    if _co_district_counter.get('Other'):
        company_locations.append({'label': 'Other', 'count': _co_district_counter['Other']})

    # ── Labor & employment ────────────────────────────────────────
    total_applications = Application.objects.count()
    # "Jobs filled" = applications that reached the terminal `hired` state,
    # which under the two-step hire flow means BOTH the employer offered
    # AND the jobseeker accepted. `accepted` (In Progress) is only the
    # employer-forward half — it doesn't count as a placement.
    jobs_filled = Application.objects.filter(status='hired').count()
    # Placement rate — hired ÷ total applications. Rounded for display.
    placement_rate = (
        round(jobs_filled / total_applications * 100, 1) if total_applications else 0
    )

    # Jobs by Industry — group OPEN jobs by their company's nature_of_company,
    # then roll up using the same NLP nature→industry clustering computed for
    # `company_natures` above ("Hospital", "Medical Clinic", etc. → Healthcare).
    # Prior version queried a non-existent `sector` field on JobPosting and
    # fell through to iterating the Sector model — showing PWD / OSY / etc.
    # (marginalized-group labels) with zero counts.
    job_nature_pairs = (JobPosting.objects
        .filter(status='open')
        .exclude(company__nature_of_company='')
        .values_list('company__nature_of_company', flat=True))
    industry_job_counter = Counter()
    for nature in job_nature_pairs:
        if nature_to_industry:
            bucket = nature_to_industry.get(nature, nature) or 'Unspecified'
        else:
            bucket = nature or 'Unspecified'
        industry_job_counter[bucket] += 1
    jobs_by_industry = [
        {'label': label, 'count': count}
        for label, count in industry_job_counter.most_common(12)
    ]

    # Jobs by location — same district roll-up. Rows whose `barangay_name` is
    # empty or purely a street noise-word fall through to the city, which then
    # resolves back to 'Other' when the city isn't recognisable.
    location_counter = Counter()
    for row in (
        JobPosting.objects
        .filter(status='open', deleted_at__isnull=True, admin_disabled=False)
        .values('barangay_name', 'city')
    ):
        raw = (row['barangay_name'] or '').strip() or (row['city'] or '').strip()
        location_counter[resolve_district(raw)] += 1
    jobs_by_location = [
        {'label': d, 'count': location_counter[d]}
        for d in DISTRICTS if location_counter[d]
    ]
    if location_counter.get('Other'):
        jobs_by_location.append({'label': 'Other', 'count': location_counter['Other']})

    def format_months(qs):
        return [
            {'month': row['month'].strftime('%b %Y'), 'count': row['count']}
            for row in qs
        ]

    return {
        'total_applicants': total_applicants,
        'men': men,
        'women': women,
        'civil_status': civil_status,
        'with_experience': with_experience,
        'without_experience': without_experience,
        'with_experience_pct': round(with_experience / total_applicants * 100) if total_applicants else 0,
        'without_experience_pct': round(without_experience / total_applicants * 100) if total_applicants else 0,
        'education_breakdown': education_breakdown,
        'new_applicants_per_month': json.dumps(format_months(new_applicants_per_month)),
        'interactions_per_month': json.dumps(format_months(interactions_per_month)),
        'avg_interactions': avg_interactions,
        'total_jobs': total_jobs,
        'local_jobs': local_jobs,
        'overseas_jobs': overseas_jobs,
        'remote_jobs': remote_jobs,
        'hard_to_fill_count': hard_to_fill_count,
        'hard_to_fill': hard_to_fill[:5],
        'in_demand_chart': in_demand_chart,
        'hard_to_fill_chart': hard_to_fill_chart,
        'in_demand_top': in_demand_top,
        'hard_to_fill_top': hard_to_fill_top,
        'sector_data': sector_data,
        'jobs_of_interest': jobs_of_interest,
        'common_skills': common_skills,
        'barangay_data': barangay_data,
        'placements': 0,
        'age_groups': age_groups,
        'total_companies': total_companies,
        'total_employers': total_employers,
        'company_types': company_types,
        'company_natures': company_natures,
        'company_locations': company_locations,
        'total_applications': total_applications,
        'jobs_filled': jobs_filled,
        'placement_rate': placement_rate,
        'jobs_by_industry': jobs_by_industry,
        'jobs_by_location': jobs_by_location,
        # ── New dashboard-style monthly series ─────────────────────
        'selected_year': selected_year,
        'available_years': available_years,
        'new_jobseekers_monthly': new_jobseekers_monthly,
        'new_employers_monthly': new_employers_monthly,
        'applications_monthly': applications_monthly,
        'placements_monthly': placements_monthly,
        'jobseekers_this_year': jobseekers_this_year,
        'employers_this_year': employers_this_year,
        'applications_this_year': applications_this_year,
        'placements_this_year': placements_this_year,
        'jobseekers_all_time': jobseekers_all_time,
        'employers_all_time': employers_all_time,
        'applications_all_time': applications_all_time,
        'placements_all_time': placements_all_time,
        # Comparison-chart series requested by panelists for line-graph views.
        'hired_monthly':          hired_monthly,
        'new_jobs_monthly':       new_jobs_monthly,
        'hired_this_year':        hired_this_year,
        'hired_all_time':         hired_all_time,
        'new_jobs_this_year':     new_jobs_this_year,
        'external_hires_this_year': external_hires_this_year,
        'external_hires_all_time':  external_hires_all_time,
        'external_hires_monthly':   external_hires_monthly,
    }


def analytics(request):
    context = get_analytics_context(request)
    context['is_authenticated'] = request.user.is_authenticated
    # Logged-in jobseekers get the sidebar-style dashboard view; everyone else
    # gets the public page with its own navbar.
    # Jobseekers and employers see the same analytics body wrapped in
    # their respective dashboard layout. Public/unauthenticated visitors
    # get the legacy single-page version.
    if request.user.is_authenticated:
        # Staff (PESO admins) see the same body wrapped in the admin shell.
        # Check is_staff first because staff users can also be jobseekers/employers
        # via legacy accounts, and we want the admin sidebar to win for them.
        if getattr(request.user, 'is_staff', False):
            # Pull admin sidebar context (pending counts, notifications feed).
            from apps.admin_panel.views import _admin_context
            context.update(_admin_context(request))
            return render(request, 'admin_panel/analytics.html', context)
        if getattr(request.user, 'is_jobseeker', False):
            return render(request, 'jobseekers/analytics.html', context)
        if getattr(request.user, 'is_employer', False):
            return render(request, 'employers/analytics.html', context)
    return render(request, 'public/analytics.html', context)


def analytics_csv(request):
    """PESO-admin CSV export of everything the analytics dashboard renders.

    One file, multiple stacked tables. Each table gets its own section
    header row (blank line + `== Section Name ==`) so Excel opens it as
    a readable multi-section sheet. Reuses `get_analytics_context()` so
    the numbers exactly match what admins see on the dashboard.
    """
    import csv
    from django.http import HttpResponse, HttpResponseForbidden

    if not (request.user.is_authenticated and getattr(request.user, 'is_staff', False)):
        return HttpResponseForbidden('Admin-only export.')

    ctx = get_analytics_context(request)
    year = ctx['selected_year']

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="easyhire-analytics-{year}.csv"'
    w = csv.writer(response)

    def section(title):
        w.writerow([])
        w.writerow([f'== {title} =='])

    MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    def monthly_row(label, series):
        w.writerow([label, *series, sum(series)])

    # ── Header block ──────────────────────────────────────────────
    w.writerow(['EasyHire Analytics Export'])
    w.writerow(['Year', year])
    w.writerow(['Generated at', ctx.get('now', '') or ''])

    # ── Monthly time series (12 months + total) ──────────────────
    section(f'Monthly Time Series ({year})')
    w.writerow(['Series', *MONTHS, 'Total'])
    monthly_row('New Jobseekers',    ctx['new_jobseekers_monthly'])
    monthly_row('New Employers',     ctx['new_employers_monthly'])
    monthly_row('New Jobs Posted',   ctx['new_jobs_monthly'])
    monthly_row('Applications',      ctx['applications_monthly'])
    monthly_row('Placements',        ctx['placements_monthly'])
    monthly_row('Hired',             ctx['hired_monthly'])
    monthly_row('Hired externally',  ctx['external_hires_monthly'])

    # ── Headline totals ──────────────────────────────────────────
    section('Headline Totals')
    w.writerow(['Metric', 'This Year', 'All Time'])
    w.writerow(['New Jobseekers',   ctx['jobseekers_this_year'],   ctx['jobseekers_all_time']])
    w.writerow(['New Employers',    ctx['employers_this_year'],    ctx['employers_all_time']])
    w.writerow(['Applications',     ctx['applications_this_year'], ctx['applications_all_time']])
    w.writerow(['Placements (accepted)', ctx['placements_this_year'], ctx['placements_all_time']])
    w.writerow(['Hired (terminal)', ctx['hired_this_year'],        ctx['hired_all_time']])
    w.writerow(['Hired externally', ctx['external_hires_this_year'], ctx['external_hires_all_time']])
    w.writerow(['Placement Rate (all time)', f"{ctx['placement_rate']}%", ''])

    # ── Jobseeker demographics ───────────────────────────────────
    section('Jobseekers by Sex')
    w.writerow(['Category', 'Count'])
    w.writerow(['Male',   ctx['men']])
    w.writerow(['Female', ctx['women']])

    section('Jobseekers by Age Group')
    w.writerow(['Age Group', 'Count'])
    for row in ctx.get('age_groups', []):
        w.writerow([row['label'], row['count']])

    section('Jobseekers by Civil Status')
    w.writerow(['Status', 'Count', 'Percent'])
    for row in ctx.get('civil_status', []):
        w.writerow([row['label'], row['count'], f"{row.get('pct', 0)}%"])

    section('Jobseekers by Work Experience')
    w.writerow(['Category', 'Count', 'Percent'])
    w.writerow(['With work experience',
                ctx['with_experience'], f"{ctx['with_experience_pct']}%"])
    w.writerow(['No work experience',
                ctx['without_experience'], f"{ctx['without_experience_pct']}%"])

    section('Jobseekers by Highest Educational Attainment')
    w.writerow(['Level', 'Count'])
    for row in ctx.get('education_breakdown', []):
        w.writerow([row['label'], row['count']])

    section('Jobseekers by District')
    w.writerow(['District', 'Count'])
    for row in ctx.get('barangay_data', []):
        w.writerow([row['barangay'], row['count']])

    section('Jobseekers by Sector')
    w.writerow(['Sector', 'Count'])
    # `sector_data` is a Sector queryset with an annotated `count` — attribute
    # access, not dict-style. (Chart template hits it via `x.label` too.)
    for row in ctx.get('sector_data', []) or []:
        w.writerow([getattr(row, 'label', ''), getattr(row, 'count', 0)])

    # ── Company demographics ─────────────────────────────────────
    section('Companies by Business Type')
    w.writerow(['Type', 'Count'])
    for row in ctx.get('company_types', []):
        w.writerow([row['label'], row['count']])

    section('Companies by Nature of Business')
    w.writerow(['Nature', 'Count'])
    for row in ctx.get('company_natures', []):
        w.writerow([row['label'], row['count']])

    section('Companies by District')
    w.writerow(['District', 'Count'])
    for row in ctx.get('company_locations', []):
        w.writerow([row['label'], row['count']])

    # ── Labor & employment ───────────────────────────────────────
    section('Jobs by Industry')
    w.writerow(['Industry', 'Count'])
    for row in ctx.get('jobs_by_industry', []):
        w.writerow([row['label'], row['count']])

    section('Jobs by District')
    w.writerow(['District', 'Count'])
    for row in ctx.get('jobs_by_location', []):
        w.writerow([row['label'], row['count']])

    section('Preferred Jobs (jobseeker résumé "Recommend Jobs Related to")')
    w.writerow(['Query', 'Count'])
    for row in ctx.get('jobs_of_interest', []):
        w.writerow([row['query'], row['count']])

    section('In-Demand Jobs (aggregate interactions)')
    w.writerow(['Job Title', 'Posts', 'Total Interactions', 'Avg / Post'])
    for row in ctx.get('in_demand_top', []):
        w.writerow([row['display'], row['post_count'],
                    row['total_interactions'], row['avg_interactions']])

    section('Hard to Fill Jobs (open 30+ days, <3 applicants)')
    w.writerow(['Job Title', 'Stuck Posts', 'Avg Days Open'])
    for row in ctx.get('hard_to_fill_top', []):
        w.writerow([row['display'], row['post_count'], row['avg_days']])

    return response