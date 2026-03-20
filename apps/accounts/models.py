from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("user_type", User.ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    JOBSEEKER = "jobseeker"
    EMPLOYER = "employer"
    ADMIN = "admin"

    USER_TYPE_CHOICES = [
        (JOBSEEKER, "Jobseeker"),
        (EMPLOYER, "Employer"),
        (ADMIN, "Admin"),
    ]

    email = models.EmailField(unique=True)
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default=JOBSEEKER)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    consented_to_terms = models.BooleanField(default=False)
    consented_at = models.DateTimeField(null=True, blank=True)

    is_imported = models.BooleanField(default=False)
    is_claimed = models.BooleanField(default=False)
    claim_token = models.CharField(max_length=128, blank=True, null=True, unique=True)

    # These fix the reverse accessor clash with Django's default auth.User
    groups = models.ManyToManyField(
        'auth.Group',
        blank=True,
        related_name='easyhire_users',
        related_query_name='easyhire_user',
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        blank=True,
        related_name='easyhire_users',
        related_query_name='easyhire_user',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.email} ({self.user_type})"

    @property
    def is_jobseeker(self): return self.user_type == self.JOBSEEKER
    @property
    def is_employer(self): return self.user_type == self.EMPLOYER
    @property
    def is_admin(self): return self.user_type == self.ADMIN