import re
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.views import View
from django.utils import timezone
from .models import User


# JOBSEEKER

class JobseekerLoginView(View):
    template_name = 'public/login_jobseeker.html'

    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/dashboard/')
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)

        if user is None:
            return render(request, self.template_name, {'error': 'invalid_credentials'})
        if user.is_employer:
            return render(request, self.template_name, {'error': 'employer_mismatch'})
        if not user.is_active:
            return render(request, self.template_name, {'error': 'inactive'})

        logout(request)
        login(request, user)
        # Remember the email so the Forgot Password page can pre-fill it.
        # 60-day cookie — outlives the session intentionally so a returning
        # user who forgot their password doesn't have to re-type.
        response = redirect('/dashboard/')
        response.set_cookie('eh_last_email', user.email, max_age=60 * 60 * 24 * 60,
                            samesite='Lax', secure=request.is_secure())
        return response


class RegisterStep1JobseekerView(View):
    template_name = 'public/register_step1_jobseeker.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('confirm_password', '')
        consented = request.POST.get('consent') == 'on'

        errors = {}
        if password != password2:
            errors['password'] = 'Passwords do not match.'
        if not consented:
            errors['consent'] = 'You must agree to the terms to continue.'
        if User.objects.filter(email=email).exists():
            errors['email'] = 'An account with this email already exists.'

        if errors:
            return render(request, self.template_name, {'errors': errors, 'email': email})

        user = User.objects.create_user(
            email=email,
            password=password,
            user_type=User.JOBSEEKER,
            consented_to_terms=True,
            consented_at=timezone.now(),
        )
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('/register/info/')


class RegisterStep2JobseekerView(View):
    template_name = 'public/register_step2_jobseeker.html'

    def get(self, request):
        if not request.user.is_authenticated or not request.user.is_jobseeker:
            return redirect('/login/')

        # If the user signed up via Google, pre-fill first/last name from the
        # OAuth profile so they don't have to re-type it. Still fully editable.
        prefill = {}
        try:
            from allauth.socialaccount.models import SocialAccount
            sa = SocialAccount.objects.filter(user=request.user, provider='google').first()
            if sa and sa.extra_data:
                given  = (sa.extra_data.get('given_name')  or '').strip()
                family = (sa.extra_data.get('family_name') or '').strip()
                # Fallback: split full 'name' if given/family aren't present.
                if not (given or family):
                    full = (sa.extra_data.get('name') or '').strip()
                    if full:
                        parts = full.split(' ', 1)
                        given = parts[0]
                        family = parts[1] if len(parts) > 1 else ''
                if given:  prefill['first_name'] = given
                if family: prefill['last_name']  = family
        except Exception:
            pass

        return render(request, self.template_name, {'prefill': prefill})

    def post(self, request):
        from apps.jobseekers.models import JobseekerProfile
        from apps.core.models import CityMunicipality, Barangay
        from datetime import datetime

        raw_date = request.POST.get('date_of_birth', '')
        try:
            date_of_birth = datetime.strptime(raw_date, '%m/%d/%Y').date()
        except ValueError:
            date_of_birth = None

        city_code = request.POST.get('city_municipality', '')
        barangay_code = request.POST.get('barangay', '')

        try:
            city_name = CityMunicipality.objects.get(code=city_code).name
        except CityMunicipality.DoesNotExist:
            city_name = city_code

        try:
            barangay_name = Barangay.objects.get(code=barangay_code).name
        except Barangay.DoesNotExist:
            barangay_name = barangay_code

        # Normalise phone: strip spaces, store as 09XXXXXXXXX
        raw_phone = request.POST.get('phone', '').replace(' ', '')
        if raw_phone and not raw_phone.startswith('0'):
            raw_phone = '0' + raw_phone

        JobseekerProfile.objects.create(
            user=request.user,
            first_name=request.POST.get('first_name', ''),
            middle_name=request.POST.get('middle_name', ''),
            last_name=request.POST.get('last_name', ''),
            suffix=request.POST.get('suffix', ''),
            sex=request.POST.get('sex', ''),
            date_of_birth=date_of_birth,
            civil_status=request.POST.get('civil_status', ''),
            house_unit=request.POST.get('house_unit', ''),
            street_barangay=request.POST.get('street_barangay', ''),
            city_municipality=city_name,
            city_code=city_code,
            province=request.POST.get('province', 'Iloilo'),
            province_code=request.POST.get('province_code', '063000000'),
            barangay=barangay_name,
            barangay_code=barangay_code,
            phone=raw_phone,
            contact_email=request.POST.get('contact_email', ''),
            profile_complete=False,
            profile_visibility='public',
            sector_badge_visibility='public',
        )
        return redirect('/dashboard/')


# EMPLOYER

class EmployerLoginView(View):
    template_name = 'employers/login.html'

    def get(self, request):
        if request.user.is_authenticated and request.user.is_employer:
            return redirect('/employers/dashboard/')
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)

        if user is None:
            return render(request, self.template_name, {
                'error': 'Invalid email or password.', 'email': email,
            })
        if not user.is_employer:
            return render(request, self.template_name, {
                'error': 'This account is not registered as an employer.', 'email': email,
            })
        if not user.is_active:
            return render(request, self.template_name, {
                'error': 'This account has been deactivated.', 'email': email,
            })

        logout(request)
        login(request, user)

        try:
            _ = user.employer_profile.company  # ensure profile exists
        except Exception:
            response = redirect('/employers/register/')
            response.set_cookie('eh_last_email', user.email, max_age=60 * 60 * 24 * 60,
                                samesite='Lax', secure=request.is_secure())
            return response

        response = redirect('/employers/dashboard/')
        response.set_cookie('eh_last_email', user.email, max_age=60 * 60 * 24 * 60,
                            samesite='Lax', secure=request.is_secure())
        return response


class EmployerRegisterStep1View(View):
    template_name = 'employers/register_step1.html'

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm_password', '')
        consent = request.POST.get('consent')
        company_name = request.POST.get('company_name', '').strip()

        errors = {}

        if not company_name:
            errors['company_name'] = 'Name of business is required.'
        if not consent:
            errors['consent'] = 'You must consent to data processing to register.'
        if password != confirm:
            errors['password'] = 'Passwords do not match.'
        if len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters.'
        if User.objects.filter(email=email).exists():
            errors['email'] = 'An account with this email already exists.'

        if errors:
            return render(request, self.template_name, {
                'errors': errors, 'email': email,
                'form': {'company_name': company_name},
            })

        request.session['employer_reg_email'] = email
        request.session['employer_reg_password'] = password
        request.session['employer_reg_company'] = company_name
        return redirect('/employers/register/info/')


class EmployerRegisterStep2View(View):
    template_name = 'employers/register_step2.html'

    def get(self, request):
        if not request.session.get('employer_reg_email'):
            return redirect('/employers/register/')
        from apps.jobseekers.models import Sector
        return render(request, self.template_name, {
            'sectors': Sector.objects.all(),
            'form': {'company_name': request.session.get('employer_reg_company', '')},
        })

    def post(self, request):
        from apps.jobseekers.models import Sector
        from apps.employers.models import Company, EmployerProfile
        from django.utils.text import slugify

        sectors = Sector.objects.all()

        if not request.session.get('employer_reg_email'):
            return redirect('/employers/register/')

        # Validate required fields
        required = {
            'company_name': 'Company name',
            'type_of_company': 'Type of company',
            'nature_of_company': 'Nature of company',
            'main_branch_address': 'Main branch address',
            'iloilo_street': 'Iloilo street',
            'iloilo_barangay': 'Iloilo branch barangay',
            'company_email': 'Company email',
            'recruitment_email': 'Recruitment email',
            'first_name': 'First name',
            'last_name': 'Last name',
            'position': 'Position',
            'phone': 'Phone',
            'rep_email': 'Representative email',
        }

        errors = {}
        for field, label in required.items():
            if not request.POST.get(field, '').strip():
                errors[field] = f'{label} is required.'

        # Phone validation — accept 10-digit (9XXXXXXXXX from the +63 prefixed
        # input), 11-digit (09XXXXXXXXX), or 12-digit (639XXXXXXXXX) formats.
        # Normalize to the 11-digit "09..." form for storage.
        phone = request.POST.get('phone', '').strip()
        phone_clean = re.sub(r'[\s\-\+]', '', phone)
        if phone:
            if re.match(r'^9\d{9}$', phone_clean):
                phone_clean = '0' + phone_clean
            elif re.match(r'^639\d{9}$', phone_clean):
                phone_clean = '0' + phone_clean[2:]
            if not re.match(r'^09\d{9}$', phone_clean):
                errors['phone'] = 'Please enter a valid 10-digit Philippine mobile number (e.g. 9171234567).'

        if errors:
            return render(request, self.template_name, {
                'errors': errors,
                'sectors': sectors,
                'form': request.POST,
                # Preserve checked sector boxes on form re-render.
                'selected_sector_ids': set(request.POST.getlist('sectors')),
            })

        try:
            # Create user
            email = request.session['employer_reg_email']
            password = request.session['employer_reg_password']
            user = User.objects.create_user(
                email=email,
                password=password,
                user_type=User.EMPLOYER,
                consented_to_terms=True,
                consented_at=timezone.now(),
            )

            # Add slug ... for better looking urls
            
            company_name = request.POST.get('company_name')
            slug = slugify(company_name)
            base_slug = slug
            counter = 1
            while Company.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            company = Company.objects.create(
                name=company_name,
                slug=slug,
                type_of_company=request.POST.get('type_of_company'),
                nature_of_company=request.POST.get('nature_of_company'),
                main_branch_address=request.POST.get('main_branch_address'),
                iloilo_bldg_unit=request.POST.get('iloilo_bldg_unit', ''),
                iloilo_street=request.POST.get('iloilo_street', ''),
                iloilo_barangay_code=request.POST.get('iloilo_barangay', ''),
                iloilo_barangay_name=request.POST.get('iloilo_barangay_name', ''),
                company_email=request.POST.get('company_email') or request.POST.get('recruitment_email'),
                recruitment_email=request.POST.get('recruitment_email'),
                verification_status=Company.PENDING,
            )

            sector_ids = request.POST.getlist('sectors')
            if sector_ids:
                company.sector_badges.set(sector_ids)

            EmployerProfile.objects.create(
                user=user,
                company=company,
                first_name=request.POST.get('first_name'),
                middle_name=request.POST.get('middle_name', ''),
                last_name=request.POST.get('last_name'),
                suffix=request.POST.get('suffix', ''),
                position=request.POST.get('position'),
                phone=phone_clean,
                email=request.POST.get('rep_email'),
                sex='M',
            )

            del request.session['employer_reg_email']
            del request.session['employer_reg_password']
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            return redirect('/employers/dashboard/')

        except Exception as e:
            return render(request, self.template_name, {
                'errors': {'system': str(e)},
                'sectors': sectors,
                'form': request.POST,
            })


# ── Shared ─────────────────────────────────────────────────────────────────────

def logout_view(request):
    # Only POST should mutate state (CSRF-protected)
    if request.method != 'POST':
        return redirect('/dashboard/' if request.user.is_authenticated else '/login/')
    logout(request)
    response = redirect('/login/')
    # Bust the back-button cache so the previous authenticated page can't be re-shown
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
