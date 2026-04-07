from django.views import View
from django.shortcuts import render, get_object_or_404
from .models import JobPosting


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
        return render(request, self.template_name, {'job': job})