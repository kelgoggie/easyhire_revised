from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from apps.employers.models import Company, VerificationDocument


def admin_login(request):
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('/admin-panel/')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)

        if user is None or not user.is_staff:
            return render(request, 'admin_panel/login.html', {
                'error': 'Invalid credentials or insufficient permissions.',
                'email': email,
            })

        login(request, user)
        return redirect('/admin-panel/')

    return render(request, 'admin_panel/login.html')


def admin_logout(request):
    logout(request)
    return redirect('/admin-panel/login/')


def staff_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return redirect('/admin-panel/login/')
        return view_func(request, *args, **kwargs)
    return wrapper


@staff_required
def dashboard(request):
    pending = Company.objects.filter(verification_status=Company.PENDING).order_by('-created_at')
    verified = Company.objects.filter(verification_status=Company.VERIFIED).order_by('-verified_at')
    denied = Company.objects.filter(verification_status=Company.DENIED).order_by('-updated_at')
    unverified = Company.objects.filter(verification_status=Company.UNVERIFIED).order_by('-created_at')

    return render(request, 'admin_panel/dashboard.html', {
        'pending': pending,
        'verified': verified,
        'denied': denied,
        'unverified': unverified,
        'pending_count': pending.count(),
    })


@staff_required
def employer_list(request):
    status = request.GET.get('status', 'pending')
    companies = Company.objects.filter(verification_status=status).order_by('-created_at')
    return render(request, 'admin_panel/employer_list.html', {
        'companies': companies,
        'current_status': status,
        'pending_count': Company.objects.filter(verification_status=Company.PENDING).count(),
    })


@staff_required
def employer_detail(request, company_id):
    company = get_object_or_404(Company, id=company_id)
    documents = VerificationDocument.objects.filter(company=company)
    uploaded_types = {doc.doc_type for doc in documents}

    required_docs = [
        VerificationDocument.MAYORS_PERMIT,
        VerificationDocument.PHILJOBNET_ACCREDITATION,
        VerificationDocument.PHILJOBNET_DASHBOARD,
        VerificationDocument.JOB_VACANCIES_LIST,
    ]
    if company.type_of_company in ['local', 'overseas']:
        required_docs += [
            VerificationDocument.PEA_LICENSE,
            VerificationDocument.DO174_CERTIFICATE,
        ]
    if company.type_of_company == 'overseas':
        required_docs += [
            VerificationDocument.POEA_LICENSE,
            VerificationDocument.JOB_ORDER,
        ]

    doc_labels = dict(VerificationDocument.DOC_TYPE_CHOICES)
    checklist = [
        {
            'type': doc_type,
            'label': doc_labels[doc_type],
            'uploaded': doc_type in uploaded_types,
            'doc': next((d for d in documents if d.doc_type == doc_type), None),
        }
        for doc_type in required_docs
    ]

    profile = company.representatives.first()

    return render(request, 'admin_panel/employer_detail.html', {
        'company': company,
        'profile': profile,
        'checklist': checklist,
        'pending_count': Company.objects.filter(verification_status=Company.PENDING).count(),
    })


@staff_required
def set_verification(request, company_id):
    if request.method != 'POST':
        return redirect('admin_panel:employer_detail', company_id=company_id)

    company = get_object_or_404(Company, id=company_id)
    new_status = request.POST.get('status')
    rejection_note = request.POST.get('rejection_note', '').strip()

    valid_statuses = [Company.UNVERIFIED, Company.PENDING, Company.DENIED, Company.VERIFIED]
    if new_status not in valid_statuses:
        return redirect('admin_panel:employer_detail', company_id=company_id)

    company.verification_status = new_status
    company.rejection_note = rejection_note if new_status == Company.DENIED else ''

    if new_status == Company.VERIFIED:
        company.verified_at = timezone.now()
        company.verified_by = request.user
    else:
        company.verified_at = None
        company.verified_by = None

    company.save()
    return redirect('admin_panel:employer_detail', company_id=company_id)