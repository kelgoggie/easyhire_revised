"""Template context processors for the accounts app."""


def email_verification_status(request):
    """Expose `user_email_verified` to all templates so the dashboard bases can
    show a "please verify your email" banner. Returns True when allauth has a
    verified EmailAddress for the current user, False otherwise.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'user_email_verified': True}
    try:
        from allauth.account.models import EmailAddress
        verified = EmailAddress.objects.filter(user=user, verified=True).exists()
    except Exception:
        # Don't ever crash a page render on a DB/import hiccup here.
        verified = True
    return {'user_email_verified': verified}
