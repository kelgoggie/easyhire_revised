"""One-shot helper to mark a user's email as verified.

Useful for demos / manual test accounts where you don't want to click
the confirmation link. ``seed_demo`` already pre-verifies its accounts,
so this is only needed for accounts created outside that flow.

Usage:
    python manage.py verify_email user@example.com
    python manage.py verify_email --all-employers
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Mark one user (by email) — or every employer — as having a verified email."

    def add_arguments(self, parser):
        parser.add_argument('email', nargs='?', default=None,
                            help='Email of the user to verify.')
        parser.add_argument('--all-employers', action='store_true',
                            help='Verify every employer account in the database. Use sparingly.')

    def handle(self, *args, **opts):
        try:
            from allauth.account.models import EmailAddress
        except ImportError:
            raise CommandError("django-allauth isn't installed.")

        User = get_user_model()

        if opts['all_employers']:
            users = list(User.objects.filter(user_type=User.EMPLOYER))
        elif opts['email']:
            users = list(User.objects.filter(email__iexact=opts['email']))
            if not users:
                raise CommandError(f"No user found with email {opts['email']!r}.")
        else:
            raise CommandError('Pass an email, or use --all-employers.')

        verified = 0
        for u in users:
            EmailAddress.objects.update_or_create(
                user=u, email=u.email,
                defaults={'verified': True, 'primary': True},
            )
            verified += 1
        self.stdout.write(self.style.SUCCESS(
            f'Marked {verified} user{"s" if verified != 1 else ""} as email-verified.'
        ))
