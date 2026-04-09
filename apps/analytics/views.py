from django.shortcuts import render
import json


def get_analytics_context(request):
    from django.utils import timezone
    from datetime import timedelta
    from django.db.models import Count
    from django.db.models.functions import TruncMonth
    from apps.jobseekers.models import JobseekerProfile, WorkExperience, Education, Skill, JobInteraction, Sector
    from apps.jobs.models import JobPosting
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
    edu_data = Education.objects.values(
        'level'
    ).annotate(count=Count('id')).order_by('-count')
    education_breakdown = [
        {
            'label': LEVEL_LABELS.get(row['level'], row['level']),
            'count': row['count'],
            'pct': round(row['count'] / total_applicants * 100) if total_applicants else 0,
        }
        for row in edu_data
    ]

    # ── Monthly stats ──────────────────────────────────────────────
    now = timezone.now()
    twelve_months_ago = now - timedelta(days=365)

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
    all_jobs = JobPosting.objects.filter(status='open')
    total_jobs = all_jobs.count()
    local_jobs = all_jobs.filter(location_type='iloilo').count()
    overseas_jobs = all_jobs.filter(location_type='overseas').count()
    remote_jobs = all_jobs.filter(location_type='remote').count()

    hard_to_fill = [job for job in all_jobs.select_related('company') if job.is_hard_to_fill]
    hard_to_fill_count = len(hard_to_fill)

    in_demand = list(
        JobPosting.objects.filter(status='open').annotate(
            interaction_count=Count('jobseeker_interactions')
        ).select_related('company').order_by('-interaction_count')[:10]
    )

    # ── Applicant insights ─────────────────────────────────────────
    sector_data = Sector.objects.annotate(
        count=Count('jobseekers')
    ).order_by('-count')

    queries = JobseekerProfile.objects.exclude(
        job_search_query=''
    ).values_list('job_search_query', flat=True)
    query_counter = Counter(q.strip().lower() for q in queries if q.strip())
    jobs_of_interest = [
        {'query': q, 'count': c}
        for q, c in query_counter.most_common(10)
    ]

    common_skills = list(
        Skill.objects.values('name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
    )

    barangay_data = list(
        JobseekerProfile.objects.exclude(
            barangay=''
        ).values('barangay').annotate(
            count=Count('id')
        ).order_by('-count')[:20]
    )

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
        'in_demand': in_demand,
        'sector_data': sector_data,
        'jobs_of_interest': jobs_of_interest,
        'common_skills': common_skills,
        'barangay_data': barangay_data,
        'placements': 0,
    }


def analytics(request):
    context = get_analytics_context(request)
    context['is_authenticated'] = request.user.is_authenticated
    return render(request, 'public/analytics.html', context)