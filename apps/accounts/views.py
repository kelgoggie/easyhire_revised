import re
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import never_cache
from django.utils import timezone
from .models import User


# JOBSEEKER

@method_decorator(never_cache, name='dispatch')
class JobseekerLoginView(View):
    template_name = 'public/login_jobseeker.html'

    def get(self, request):
        if request.user.is_authenticated:
            # Route to the correct dashboard for the account's role. Without
            # the is_staff / is_employer branches an admin who truncates
            # /admin-panel/ off a URL falls through to /dashboard/ and can
            # land on whichever JobseekerProfile happens to be linked to
            # their user row — a security-shaped bug even when the outcome
            # is "your own profile", because the intent is admin panel.
            if request.user.is_staff:
                return redirect('/admin-panel/')
            if request.user.is_employer:
                return redirect('/employers/dashboard/')
            return redirect('/dashboard/')
        # `?error=inactive` is set by the allauth override at
        # templates/account/account_inactive.html when a disabled user
        # tries to sign in via Google OAuth — surfaces the same red
        # banner shown on failed email/password attempts instead of
        # dumping them on allauth's generic "Account Inactive" page.
        ctx = {}
        err = (request.GET.get('error') or '').strip().lower()
        if err in ('inactive', 'invalid_credentials', 'employer_mismatch', 'staff_mismatch'):
            ctx['error'] = err
        return render(request, self.template_name, ctx)

    def post(self, request):
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)

        if user is None:
            return render(request, self.template_name, {'error': 'invalid_credentials'})
        if user.is_staff:
            return render(request, self.template_name, {'error': 'staff_mismatch'})
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
        # Duplicate-email check: EasyHire allows exactly one account per
        # email address across the whole platform. Surface the owning
        # account type so the user knows which login flow to use rather
        # than getting a generic "already exists" that reads like a bug.
        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            if existing.user_type == User.EMPLOYER:
                errors['email'] = (
                    'This email is already registered as an Employer. '
                    'Sign in with your employer account, or use a different email.'
                )
            elif existing.user_type == User.JOBSEEKER:
                errors['email'] = 'You already have a jobseeker account with this email. Sign in instead.'
            else:
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
        # Email verification is retired. PESO's ID-upload workflow is the
        # authoritative identity signal for jobseekers, so we mark the
        # allauth EmailAddress row verified up front — no confirmation
        # email is ever queued, the "Verify your email" banner never
        # shows, and every SMTP-shaped failure mode disappears with it.
        try:
            from allauth.account.models import EmailAddress
            EmailAddress.objects.update_or_create(
                user=user, email=user.email,
                defaults={'verified': True, 'primary': True},
            )
        except Exception:
            import logging
            logging.getLogger(__name__).exception('EmailAddress bootstrap failed for %s', email)
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

        # Prefill the Contact Email field with the account email the user
        # signed up with (or their Google OAuth email). Field stays editable —
        # they can override if their preferred contact email differs.
        return render(request, self.template_name, {
            'prefill': prefill,
            'session_email': request.user.email or '',
        })

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

@method_decorator(never_cache, name='dispatch')
class EmployerLoginView(View):
    template_name = 'employers/login.html'

    def get(self, request):
        if request.user.is_authenticated:
            if request.user.is_staff:
                return redirect('/admin-panel/')
            if request.user.is_employer:
                return redirect('/employers/dashboard/')
            # Authenticated jobseeker landed on the employer login page — send
            # them to their own dashboard rather than showing an interstitial.
            if request.user.is_jobseeker:
                return redirect('/dashboard/')
        return render(request, self.template_name)

    def post(self, request):
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)

        if user is None:
            return render(request, self.template_name, {
                'error': 'Invalid email or password.', 'email': email,
            })
        if user.is_staff:
            return render(request, self.template_name, {
                'error': 'Admin accounts sign in at /admin-panel/login/.', 'email': email,
            })
        if not user.is_employer:
            return render(request, self.template_name, {
                'error': 'This account is not registered as an employer.', 'email': email,
            })
        if not user.is_active:
            return render(request, self.template_name, {
                'error': (
                    'Your account has been disabled. Contact '
                    'easyhire.admin@gmail.com for more information.'
                ),
                'email': email,
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
        # Same cross-type collision guard as the jobseeker signup — one
        # account per email, and the message tells the user which side
        # already owns it.
        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            if existing.user_type == User.JOBSEEKER:
                errors['email'] = (
                    'This email is already registered as a Jobseeker. '
                    'Sign in with your jobseeker account, or use a different email.'
                )
            elif existing.user_type == User.EMPLOYER:
                errors['email'] = 'You already have an employer account with this email. Sign in instead.'
            else:
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

    def _oauth_bypass(self, request):
        """Employers who signed in via Google skip step 1 entirely — no
        email + password form, no session prefill. This view accepts the
        request when the user is already authenticated as an employer
        without an EmployerProfile yet. Returns True in that case so both
        GET and POST accept the OAuth-driven caller.
        """
        u = request.user
        if not u.is_authenticated or not u.is_employer:
            return False
        try:
            _ = u.employer_profile
            return False  # already has a profile — no reason to be here
        except Exception:
            return True

    def get(self, request):
        oauth_flow = self._oauth_bypass(request)
        if not request.session.get('employer_reg_email') and not oauth_flow:
            return redirect('/employers/register/')
        from apps.jobseekers.models import Sector
        # Prefill Company Email + Recruitment Email with whatever email the
        # signup started from — session for the email/password path, the
        # authenticated user for the OAuth path. Both fields stay editable.
        signup_email = (
            request.user.email if oauth_flow
            else request.session.get('employer_reg_email', '')
        ) or ''
        return render(request, self.template_name, {
            'sectors': Sector.objects.all(),
            # OAuth users start with a blank company_name; email/password
            # form-step users get their name pre-filled from step 1.
            'form': {
                'company_name': '' if oauth_flow else request.session.get('employer_reg_company', ''),
                'company_email': signup_email,
                'recruitment_email': signup_email,
            },
            'oauth_flow': oauth_flow,
        })

    def post(self, request):
        from apps.jobseekers.models import Sector
        from apps.employers.models import Company, EmployerProfile
        from django.utils.text import slugify

        sectors = Sector.objects.all()
        oauth_flow = self._oauth_bypass(request)

        if not request.session.get('employer_reg_email') and not oauth_flow:
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
            # OAuth-driven employer signup: user already exists (allauth
            # created them via the Google flow, and populate_user promoted
            # user_type to 'employer' when the intent was set). Just take
            # the current authenticated user.
            if oauth_flow:
                user = request.user
                email = user.email
                # Ensure user_type is set correctly — populate_user may not
                # have run if this User existed with a jobseeker user_type
                # from earlier. Explicit here so the profile check downstream
                # (is_employer) succeeds.
                if user.user_type != User.EMPLOYER:
                    user.user_type = User.EMPLOYER
                    user.save(update_fields=['user_type'])
            else:
                # Standard email + password flow — step 1 stashed creds
                # in the session; create the User now.
                email = request.session['employer_reg_email']
                password = request.session['employer_reg_password']
                user = User.objects.create_user(
                    email=email,
                    password=password,
                    user_type=User.EMPLOYER,
                    consented_to_terms=True,
                    consented_at=timezone.now(),
                )
            # Employer email verification is skipped by design — the
            # docs-based Company verification workflow (Mayor's Permit,
            # PhilJobNet accreditation, etc.) is a much stronger identity
            # signal than an email link. Mark the EmailAddress row
            # verified up-front so the "please verify your email" banner
            # never shows for employers, and no confirmation email goes
            # out on signup.
            try:
                from allauth.account.models import EmailAddress
                EmailAddress.objects.update_or_create(
                    user=user, email=user.email,
                    defaults={'verified': True, 'primary': True},
                )
            except Exception:
                import logging
                logging.getLogger(__name__).exception('Employer EmailAddress bootstrap failed for %s', email)

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

def employer_google_login(request):
    """Intent-tagged entry point for the "Sign in with Google" button on
    the employer login page. Stashes `oauth_intent='employer'` in the
    session so SocialAccountAdapter.populate_user knows to promote the
    new user's user_type to EMPLOYER instead of the default JOBSEEKER.
    Then hands off to allauth's standard Google login URL.
    """
    request.session['oauth_intent'] = 'employer'
    return redirect('/accounts/google/login/?process=login')


@never_cache
def password_recovery(request):
    """PESO-mediated password recovery info page.

    Renders a static info page. The `prefill` value is what the "Forgot
    password" click on the sign-in page carries over — either via `?email=`
    or the `eh_last_email` cookie set on the last successful login. Locking
    the reset input to that email prevents a shared-machine attacker from
    typing an arbitrary address and blasting a reset link to it.

    Prefill lookup was inlined in the template as
    `request.GET.email|default:request.COOKIES.eh_last_email|default:''` —
    but `{% with %}` doesn't swallow VariableDoesNotExist the way plain
    interpolation does, so the page crashed the moment the cookie wasn't
    set. Moved to the view so it's expressed in plain Python.
    """
    prefill = (
        (request.GET.get('email') or '').strip()
        or (request.COOKIES.get('eh_last_email') or '').strip()
    )
    return render(request, 'public/password_recovery.html', {'prefill': prefill})


def logout_view(request):
    # Only POST should mutate state (CSRF-protected)
    if request.method != 'POST':
        return redirect('/dashboard/' if request.user.is_authenticated else '/login/')
    # Route the logged-out user back to the login page that matches their
    # role — a company rep dropped on the jobseeker sign-in is confusing.
    # Read the flag BEFORE logout() blows the session away.
    was_employer = request.user.is_authenticated and getattr(request.user, 'is_employer', False)
    logout(request)
    response = redirect('/employers/login/' if was_employer else '/login/')
    # Bust the back-button cache so the previous authenticated page can't be re-shown
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    # Explicitly delete the session + CSRF cookies. `logout(request)` clears
    # the session server-side but doesn't always tell the browser to drop
    # the cookie — some flows saw the stale sessionid re-authenticating on
    # the very next request. Safer to blow them away by hand.
    from django.conf import settings as _settings
    response.delete_cookie(
        _settings.SESSION_COOKIE_NAME,
        path=_settings.SESSION_COOKIE_PATH,
        domain=_settings.SESSION_COOKIE_DOMAIN,
    )
    response.delete_cookie(
        _settings.CSRF_COOKIE_NAME,
        path=_settings.CSRF_COOKIE_PATH,
        domain=_settings.CSRF_COOKIE_DOMAIN,
    )
    return response
