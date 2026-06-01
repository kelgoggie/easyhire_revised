from django.views import View
from django.shortcuts import render, get_object_or_404
from .models import JobPosting

from apps.matching.engine import (
    compute_match_score,
    WEIGHT_SKILLS, WEIGHT_EDUCATION,
    WEIGHT_EXPERIENCE, WEIGHT_CERTIFICATIONS,
)


class PublicJobListView(View):
    template_name = 'public/jobs.html'

    def get(self, request):
        jobs = JobPosting.objects.filter(status=JobPosting.STATUS_OPEN).select_related(
            'company',
            'education_requirement',
            'experience_requirement',
        ).prefetch_related(
            'skill_requirements',
            'certification_requirements',
        )

        # Filters
        search = request.GET.get('q', '').strip()
        location_type = request.GET.get('location', '')
        sector = request.GET.get('sector', '')

        if search:
            jobs = jobs.filter(title__icontains=search) | jobs.filter(company__name__icontains=search)
        if location_type:
            jobs = jobs.filter(location_type=location_type)
        if sector:
            jobs = jobs.filter(company__sector_badges__id=sector)

        # Collect unique sectors for filter dropdown
        from apps.jobseekers.models import Sector
        sectors = Sector.objects.all().order_by('label')

        return render(request, self.template_name, {
            'jobs': jobs,
            'sectors': sectors,
            'search': search,
            'location_type': location_type,
            'sector': sector,
            'total': jobs.count(),
        })


class PublicJobDetailView(View):
    template_name = 'public/job_detail.html'

    def get(self, request, pk):
        all_jobs = list(JobPosting.objects.filter(
            status=JobPosting.STATUS_OPEN
        ).order_by('-created_at').values_list('id', flat=True))

        job = get_object_or_404(
            JobPosting.objects.select_related(
                'company',
                'education_requirement',
                'experience_requirement',
            ).prefetch_related(
                'skill_requirements',
                'certification_requirements',
            ),
            pk=pk,
            status=JobPosting.STATUS_OPEN,
        )

        # Prev/next
        try:
            current_index = all_jobs.index(job.id)
            prev_job_id = all_jobs[current_index + 1] if current_index + 1 < len(all_jobs) else None
            next_job_id = all_jobs[current_index - 1] if current_index > 0 else None
        except ValueError:
            prev_job_id = next_job_id = None

        prev_job = JobPosting.objects.filter(id=prev_job_id).first() if prev_job_id else None
        next_job = JobPosting.objects.filter(id=next_job_id).first() if next_job_id else None

        # Liked/hidden + match score
        liked_ids = set()
        hidden_ids = set()
        match_score = None

        if request.user.is_authenticated and hasattr(request.user, 'is_jobseeker') and request.user.is_jobseeker:
            try:
                from apps.jobseekers.models import JobInteraction
                from apps.matching.engine import compute_match_score
                profile = request.user.jobseeker_profile
                liked_ids = set(JobInteraction.objects.filter(
                    jobseeker=profile, interaction_type=JobInteraction.LIKED
                ).values_list('job_id', flat=True))
                hidden_ids = set(JobInteraction.objects.filter(
                    jobseeker=profile, interaction_type=JobInteraction.HIDDEN
                ).values_list('job_id', flat=True))
                if profile.profile_complete:
                    match_score = compute_match_score(job, profile)
            except Exception:
                pass


        return render(request, self.template_name, {
            'job': job,
            'liked_ids': liked_ids,
            'hidden_ids': hidden_ids,
            'match_score': match_score,
            'prev_job': prev_job,
            'next_job': next_job,
            'weights': {
                'skills': round(WEIGHT_SKILLS * 100),
                'education': round(WEIGHT_EDUCATION * 100),
                'experience': round(WEIGHT_EXPERIENCE * 100),
                'certifications': round(WEIGHT_CERTIFICATIONS * 100),
            }
        })

class JobseekerJobDetailView(View):
    template_name = 'jobseekers/job_detail.html'

    def get(self, request, pk):
        if not request.user.is_authenticated or not request.user.is_jobseeker:
            return redirect(f'/jobs/{pk}/')

        job = get_object_or_404(
            JobPosting.objects.select_related(
                'company',
                'education_requirement',
                'experience_requirement',
            ).prefetch_related(
                'skill_requirements',
                'certification_requirements',
            ),
            pk=pk,
            status=JobPosting.STATUS_OPEN,
        )

        all_jobs = list(JobPosting.objects.filter(
            status=JobPosting.STATUS_OPEN
        ).order_by('-created_at').values_list('id', flat=True))

        try:
            current_index = all_jobs.index(job.id)
            prev_job_id = all_jobs[current_index + 1] if current_index + 1 < len(all_jobs) else None
            next_job_id = all_jobs[current_index - 1] if current_index > 0 else None
        except ValueError:
            prev_job_id = next_job_id = None

        prev_job = JobPosting.objects.filter(id=prev_job_id).first() if prev_job_id else None
        next_job = JobPosting.objects.filter(id=next_job_id).first() if next_job_id else None

        from apps.jobseekers.models import JobInteraction
        profile = request.user.jobseeker_profile
        liked_ids = set(JobInteraction.objects.filter(
            jobseeker=profile, interaction_type=JobInteraction.LIKED
        ).values_list('job_id', flat=True))
        hidden_ids = set(JobInteraction.objects.filter(
            jobseeker=profile, interaction_type=JobInteraction.HIDDEN
        ).values_list('job_id', flat=True))

        match_score = None
        if profile.profile_complete:
            from apps.matching.engine import compute_match_score
            match_score = compute_match_score(job, profile)

        return render(request, self.template_name, {
            'job': job,
            'liked_ids': liked_ids,
            'hidden_ids': hidden_ids,
            'match_score': match_score,
            'prev_job': prev_job,
            'next_job': next_job,
            'weights': {
                'skills': round(WEIGHT_SKILLS * 100),
                'education': round(WEIGHT_EDUCATION * 100),
                'experience': round(WEIGHT_EXPERIENCE * 100),
                'certifications': round(WEIGHT_CERTIFICATIONS * 100),
            }
        })