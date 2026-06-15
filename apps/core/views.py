from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Province, CityMunicipality, Barangay


@login_required
def help_view(request):
    if request.user.is_employer:
        return render(request, 'employers/help.html')
    return render(request, 'jobseekers/help.html')


@login_required
def inbox(request):
    """Unified inbox combining applications, interview schedules, and admin
    announcements. Forks by user type. Each item normalized to a common shape
    so the same template row renders all three sources.
    """
    from apps.admin_panel.models import AdminAnnouncement
    from apps.employers.models import EmployerContact
    from apps.jobs.models import Application
    from apps.core.pagination import paginate, querystring_without

    items = []
    user = request.user

    if user.is_jobseeker:
        try:
            profile = user.jobseeker_profile
        except Exception:
            return redirect('/register/info/')

        # Applications the jobseeker sent
        for app in (Application.objects
                    .filter(jobseeker=profile)
                    .select_related('job', 'job__company')):
            items.append({
                'kind': 'application_sent',
                'actor': 'You',
                'verb': f'applied to "{app.job.title}" at {app.job.company.name}.',
                'context': app.status,
                'timestamp': app.created_at,
                'url': '/applications/',
                'report_target_type': '',
                'report_target_id': None,
                'report_label': '',
            })

        # Employer contacts received (requirements + interview schedules)
        for contact in (EmployerContact.objects
                        .filter(recipient=profile)
                        .select_related('company', 'sender', 'job')):
            sender_name = ''
            if contact.sender:
                prof = getattr(contact.sender, 'employer_profile', None)
                if prof:
                    sender_name = f"{prof.first_name} {prof.last_name}".strip()
            actor = sender_name or contact.company.name
            verb = (f'sent you {"interview details" if contact.kind == EmployerContact.KIND_INTERVIEW else "job requirements"}.')
            items.append({
                'kind': contact.kind,
                'actor': actor,
                'verb': verb,
                'context': contact.subject,
                'timestamp': contact.sent_at,
                'url': '/inbox/',
                'detail_body': contact.body,
                'detail_interview_at': contact.interview_at,
                'detail_interview_location': contact.interview_location,
                'detail_company': contact.company.name,
                'report_target_type': 'employer',
                'report_target_id': contact.company.id,
                'report_label': f'Re: {contact.subject}',
            })

        # Admin announcements targeting jobseekers (or all)
        for ann in AdminAnnouncement.objects.filter(
            audience__in=[AdminAnnouncement.AUDIENCE_ALL, AdminAnnouncement.AUDIENCE_JOBSEEKERS]
        ):
            items.append({
                'kind': 'announcement',
                'actor': 'PESO Iloilo City',
                'verb': 'sent an announcement.',
                'context': ann.subject,
                'timestamp': ann.sent_at,
                'url': '/inbox/',
                'detail_body': ann.body,
                'report_target_type': '',
                'report_target_id': None,
                'report_label': '',
            })

        template = 'jobseekers/inbox.html'

    elif user.is_employer:
        try:
            employer_profile = user.employer_profile
        except Exception:
            return redirect('/employers/login/')
        company = employer_profile.company

        # Applications received on this company's job posts
        for app in (Application.objects
                    .filter(job__company=company)
                    .select_related('job', 'jobseeker')):
            jname = f"{app.jobseeker.first_name} {app.jobseeker.last_name}".strip() if app.jobseeker else 'Someone'
            items.append({
                'kind': 'application_received',
                'actor': jname,
                'verb': f'sent a Job Application: "{app.job.title}".',
                'context': app.status,
                'timestamp': app.created_at,
                'url': f'/employers/jobs/{app.job.id}/candidates/?tab=applicants',
                'report_target_type': 'jobseeker',
                'report_target_id': app.jobseeker.id if app.jobseeker else None,
                'report_label': f'Re: application to {app.job.title}',
            })

        # Contacts the company has sent
        for contact in (EmployerContact.objects
                        .filter(company=company)
                        .select_related('recipient', 'job', 'sender')):
            jname = ''
            if contact.recipient:
                jname = f"{contact.recipient.first_name} {contact.recipient.last_name}".strip()
            kind_label = 'an Interview' if contact.kind == EmployerContact.KIND_INTERVIEW else 'Job Requirements'
            items.append({
                'kind': contact.kind,
                'actor': jname or 'Candidate',
                'verb': f'You scheduled {kind_label}.' if contact.kind == EmployerContact.KIND_INTERVIEW else f'You sent {kind_label}.',
                'context': contact.subject,
                'timestamp': contact.sent_at,
                'url': f'/employers/candidates/{contact.recipient.id}/' if contact.recipient else '/inbox/',
                'detail_body': contact.body,
                'detail_interview_at': contact.interview_at,
                'detail_interview_location': contact.interview_location,
                'report_target_type': '',
                'report_target_id': None,
                'report_label': '',
            })

        # Admin announcements targeting employers (or all)
        for ann in AdminAnnouncement.objects.filter(
            audience__in=[AdminAnnouncement.AUDIENCE_ALL, AdminAnnouncement.AUDIENCE_EMPLOYERS]
        ):
            items.append({
                'kind': 'announcement',
                'actor': 'PESO Iloilo City',
                'verb': 'sent an announcement.',
                'context': ann.subject,
                'timestamp': ann.sent_at,
                'url': '/inbox/',
                'detail_body': ann.body,
                'report_target_type': '',
                'report_target_id': None,
                'report_label': '',
            })

        template = 'employers/inbox.html'

    else:
        # Staff users — kick them to the admin panel where they compose announcements.
        return redirect('/admin-panel/announcements/')

    # Newest first
    items.sort(key=lambda x: x['timestamp'], reverse=True)
    page = paginate(request, items, per_page=15)

    return render(request, template, {
        'items': list(page.object_list),
        'page': page,
        'qs_base': querystring_without(request, 'page'),
        'unread_notifications': False,
        'unread_messages': False,
    })


def provinces_api(request):
    provinces = Province.objects.values('code', 'name')
    return JsonResponse(list(provinces), safe=False)


def cities_api(request, province_code):
    cities = CityMunicipality.objects.filter(
        province__code=province_code
    ).values('code', 'name')
    return JsonResponse(list(cities), safe=False)


def barangays_api(request, city_code):
    barangays = Barangay.objects.filter(
        city__code=city_code
    ).values('code', 'name')
    return JsonResponse(list(barangays), safe=False)