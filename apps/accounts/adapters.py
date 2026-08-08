import logging
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.utils import timezone


# Domains reserved for demo / seeded accounts. Any allauth email addressed
# to one of these skips SMTP entirely — no MX records exist for `.test`
# (RFC 2606), so Gmail hangs on DNS long enough to trip Render's proxy.
_SKIP_SMTP_SUFFIXES = ('@easyhire.test', '@easyhire.extra', '@easyhire.local')


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return True

    def send_mail(self, template_prefix, email, context):
        """Central hook allauth uses for every outbound email — confirmation
        links on signup, password reset links, resend-confirmation, email
        change notices. Overriding here means we don't have to sprinkle the
        `.test`-domain guard through every caller:

          - test/demo domains → log & no-op (never touch SMTP)
          - real domains → call the parent, but swallow SMTPExceptions so
            a bad relay doesn't take down user-facing views (e.g. the
            password recovery form's redirect to "check your email").

        Every allauth-triggered email path now completes without leaking a
        500 back to the browser.
        """
        low = (email or '').strip().lower()
        if any(low.endswith(s) for s in _SKIP_SMTP_SUFFIXES):
            logging.getLogger(__name__).info(
                '[allauth] skipping SMTP for demo/test recipient: %s (%s)',
                email, template_prefix,
            )
            return
        try:
            super().send_mail(template_prefix, email, context)
        except Exception as exc:
            logging.getLogger(__name__).exception(
                '[allauth] send_mail failed for %s (%s): %s',
                email, template_prefix, exc,
            )
            # Swallow — the flow that triggered this send (password reset,
            # signup, resend) still returns success to the user. The
            # in-app fallback (PESO-mediated recovery) exists precisely for
            # this case.
            return

    def get_login_redirect_url(self, request):
        user = request.user
        if not user.is_authenticated:
            return '/login/'
        # Staff first — admins may also carry a jobseeker/employer user_type
        # from earlier in their account's life; the panel is where they
        # belong regardless.
        if user.is_staff:
            return '/admin-panel/'
        # NOTE: `user_type` is stored lowercase (see User.JOBSEEKER = 'jobseeker'
        # in apps/accounts/models.py). Previously compared to the uppercase
        # string, which always failed and dumped every OAuth login on
        # /dashboard/ regardless of role.
        if user.user_type == 'jobseeker':
            try:
                _ = user.jobseeker_profile
                return '/dashboard/'
            except Exception:
                return '/register/info/'
        if user.user_type == 'employer':
            try:
                _ = user.employer_profile.company
                return '/employers/dashboard/'
            except Exception:
                return '/employers/register/'
        return '/dashboard/'

    def save_user(self, request, user, form=None, commit=True):
        data = form.cleaned_data if form else {}
        email = data.get('email') or getattr(user, 'email', '')
        if email:
            user.email = email
        if commit:
            user.save()
        return user


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        """Populate the User from a Google-issued profile. `user_type` is
        set from `request.session['oauth_intent']` — the employer login
        page's "Sign in with Google" button routes through
        /employers/google-login/ which stamps that flag before the OAuth
        redirect. Anywhere else defaults to jobseeker.
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = sociallogin.user
        user.email = data.get('email', '')
        intent = (request.session.get('oauth_intent') or '').strip().lower() if request else ''
        if intent == 'employer':
            user.user_type = User.EMPLOYER
        else:
            user.user_type = User.JOBSEEKER
        user.consented_to_terms = True
        user.consented_at = timezone.now()
        return user

    def is_auto_signup_allowed(self, request, sociallogin):
        return True

    def pre_social_login(self, request, sociallogin):
        """Block OAuth sign-in when the Google account's email is already
        used by a local account of a DIFFERENT type. One email = one
        account role on EasyHire, and this guard makes the OAuth path
        honour that just like the email/password signup flows do.

        The check fires only when there's a role mismatch — a jobseeker
        signing in with Google to their own jobseeker account still
        auto-connects normally (SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT).
        """
        from allauth.exceptions import ImmediateHttpResponse
        from django.contrib.auth import get_user_model
        from django.shortcuts import redirect
        from django.contrib import messages
        User = get_user_model()

        email = (sociallogin.user.email or '').strip().lower()
        if not email:
            return
        existing = User.objects.filter(email__iexact=email).first()
        if not existing:
            return
        intent = (request.session.get('oauth_intent') or '').strip().lower() if request else ''
        desired_type = User.EMPLOYER if intent == 'employer' else User.JOBSEEKER
        if existing.user_type == desired_type:
            return  # normal auto-connect path — same-role reconnection is fine

        # Staff accounts always own the email; if a staff email tries to
        # sign in via a jobseeker / employer OAuth page, kick them to the
        # admin login instead.
        if existing.is_staff:
            messages.error(request, 'This email belongs to a PESO admin account. Use the admin sign-in page.')
            raise ImmediateHttpResponse(redirect('/admin-panel/login/'))

        # Cross-role collision — surface a flash and send the user to the
        # login page that MATCHES the account they already own.
        owner = 'Jobseeker' if existing.user_type == User.JOBSEEKER else 'Employer'
        target = '/login/' if existing.user_type == User.JOBSEEKER else '/employers/login/'
        messages.error(
            request,
            f'This email is already registered as a {owner}. '
            f'Sign in with your {owner.lower()} account, or use a different email to register.',
        )
        raise ImmediateHttpResponse(redirect(target))
