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
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = sociallogin.user
        user.email = data.get('email', '')
        user.user_type = User.JOBSEEKER
        user.consented_to_terms = True
        user.consented_at = timezone.now()
        return user

    def is_auto_signup_allowed(self, request, sociallogin):
        return True
