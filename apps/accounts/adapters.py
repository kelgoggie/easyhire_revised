from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.utils import timezone


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return True

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
