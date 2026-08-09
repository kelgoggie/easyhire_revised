from django.db import models
from django.conf import settings


class InboxUserState(models.Model):
    """Per-user overlay on inbox rows sourced from Application /
    EmployerContact / AdminAnnouncement. The source rows themselves are
    shared with the other party (jobseeker ↔ employer) or with the whole
    audience (announcements), so we can't delete them when a single user
    hides them from their inbox — this table records their view choices
    instead.

    - is_dismissed = True → row does not appear in this user's inbox.
    - is_pinned    = True → row floats above unpinned rows.
    - is_permanent = True → row is permanently hidden. Implies is_dismissed
      but also skips the Deleted tab AND the 30-day auto-purge, so the
      source row never comes back into the user's view.

    (user, source_type, source_id) is unique.
    """
    SOURCE_APPLICATION  = 'application'
    SOURCE_CONTACT      = 'contact'
    SOURCE_ANNOUNCEMENT = 'announcement'
    SOURCE_VERIFICATION = 'verification'
    SOURCE_CHOICES = [
        (SOURCE_APPLICATION,  'Application'),
        (SOURCE_CONTACT,      'Employer Contact'),
        (SOURCE_ANNOUNCEMENT, 'Admin Announcement'),
        (SOURCE_VERIFICATION, 'Verification Update'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inbox_states')
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    source_id   = models.PositiveIntegerField()
    is_dismissed = models.BooleanField(default=False)
    is_pinned    = models.BooleanField(default=False)
    is_permanent = models.BooleanField(default=False)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inbox_user_state'
        unique_together = [('user', 'source_type', 'source_id')]
        indexes = [
            models.Index(fields=['user', 'is_dismissed']),
            models.Index(fields=['user', 'is_pinned']),
        ]


class Province(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)

    class Meta:
        db_table = "provinces"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CityMunicipality(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    province = models.ForeignKey(
        Province, on_delete=models.CASCADE, related_name="cities"
    )

    class Meta:
        db_table = "cities_municipalities"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Barangay(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    city = models.ForeignKey(
        CityMunicipality, on_delete=models.CASCADE, related_name="barangays"
    )

    class Meta:
        db_table = "barangays"
        ordering = ["name"]

    def __str__(self):
        return self.name