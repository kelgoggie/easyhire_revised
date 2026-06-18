"""Idempotently create / update the PESO admin superuser from env vars.

Designed for Render's free tier (no Shell access) — drop into the build
command and it'll create the account on first deploy, then no-op on
every subsequent deploy.

Required env vars:
    SUPERUSER_EMAIL     — email + login identifier
    SUPERUSER_PASSWORD  — initial password (only set on creation)

Optional:
    SUPERUSER_RESET_PASSWORD=1  — also reset the password on every run
                                  (use once if you forgot it, then unset)

If the env vars aren't set, the command exits cleanly so it can stay in
the build command on environments where you don't want a seeded admin.
"""
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create or update the PESO admin superuser from SUPERUSER_EMAIL / SUPERUSER_PASSWORD env vars.'

    def handle(self, *args, **opts):
        email = (os.environ.get('SUPERUSER_EMAIL') or '').strip().lower()
        password = os.environ.get('SUPERUSER_PASSWORD') or ''

        if not email or not password:
            self.stdout.write(self.style.WARNING(
                'SUPERUSER_EMAIL / SUPERUSER_PASSWORD not set — skipping.'
            ))
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            email=email,
            defaults={'is_staff': True, 'is_superuser': True, 'is_active': True},
        )

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created superuser {email}.'))
            return

        # Already exists — make sure staff/superuser flags are still on.
        changed = []
        if not user.is_staff:
            user.is_staff = True
            changed.append('is_staff')
        if not user.is_superuser:
            user.is_superuser = True
            changed.append('is_superuser')
        if not user.is_active:
            user.is_active = True
            changed.append('is_active')

        if os.environ.get('SUPERUSER_RESET_PASSWORD') == '1':
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(
                f'Superuser {email} already existed — password reset.'
            ))
            return

        if changed:
            user.save(update_fields=changed)
            self.stdout.write(self.style.SUCCESS(
                f'Superuser {email} already existed — re-promoted ({", ".join(changed)}).'
            ))
        else:
            self.stdout.write(f'Superuser {email} already exists — no change.')
