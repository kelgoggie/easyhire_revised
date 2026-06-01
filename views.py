from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.views import View
from .models import User


class JobseekerLoginView(View):
    template_name = "public/login_jobseeker.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("jobseekers:dashboard")
        return render(request, self.template_name)

    def post(self, request):
        email    = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user     = authenticate(request, username=email, password=password)

        if user is None:
            return render(request, self.template_name, {"error": "invalid_credentials"})

        if user.is_employer:
            # Friendly mismatch message with link to employer login
            return render(request, self.template_name, {"error": "employer_mismatch"})

        if not user.is_active:
            return render(request, self.template_name, {"error": "inactive"})

        login(request, user)
        return redirect("jobseekers:dashboard")


class EmployerLoginView(View):
    template_name = "public/login_employer.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("employers:dashboard")
        return render(request, self.template_name)

    def post(self, request):
        email    = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        user     = authenticate(request, username=email, password=password)

        if user is None:
            return render(request, self.template_name, {"error": "invalid_credentials"})

        if user.is_jobseeker:
            # Reverse mismatch — they're a jobseeker on the employer login page
            return render(request, self.template_name, {"error": "jobseeker_mismatch"})

        if not user.is_active:
            return render(request, self.template_name, {"error": "inactive"})

        login(request, user)
        return redirect("employers:dashboard")


class RegisterStep1View(View):
    """Email + password + consent — shared first step for jobseekers."""
    template_name = "public/register_step1.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email     = request.POST.get("email", "").strip()
        password  = request.POST.get("password", "")
        password2 = request.POST.get("confirm_password", "")
        consented = request.POST.get("consent") == "on"

        errors = {}
        if password != password2:
            errors["password"] = "Passwords do not match."
        if not consented:
            errors["consent"] = "You must agree to the terms to continue."
        if User.objects.filter(email=email).exists():
            errors["email"] = "An account with this email already exists."

        if errors:
            return render(request, self.template_name, {"errors": errors, "email": email})

        from django.utils import timezone
        user = User.objects.create_user(
            email=email,
            password=password,
            user_type=User.JOBSEEKER,
            consented_to_terms=True,
            consented_at=timezone.now(),
        )
        login(request, user)
        return redirect("accounts:register_step2")


class RegisterStep2JobseekerView(View):
    """Personal info — completes jobseeker registration."""
    template_name = "public/register_step2_jobseeker.html"

    def get(self, request):
        if not request.user.is_authenticated or not request.user.is_jobseeker:
            return redirect("accounts:login")
        return render(request, self.template_name)

    def post(self, request):
        from apps.jobseekers.models import JobseekerProfile
        profile = JobseekerProfile.objects.create(
            user              = request.user,
            first_name        = request.POST.get("first_name", ""),
            middle_name       = request.POST.get("middle_name", ""),
            last_name         = request.POST.get("last_name", ""),
            suffix            = request.POST.get("suffix", ""),
            sex               = request.POST.get("sex", ""),
            date_of_birth     = request.POST.get("date_of_birth") or None,
            civil_status      = request.POST.get("civil_status", ""),
            house_unit        = request.POST.get("house_unit", ""),
            street_barangay   = request.POST.get("street_barangay", ""),
            city_municipality = request.POST.get("city_municipality", "Iloilo City"),
            province          = request.POST.get("province", "Iloilo"),
            phone             = request.POST.get("phone", ""),
            profile_complete  = False,
        )
        return redirect("jobseekers:resume")


class EmployerRegisterStep1View(View):
    template_name = "public/employer_register_step1.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email     = request.POST.get("email", "").strip()
        password  = request.POST.get("password", "")
        password2 = request.POST.get("confirm_password", "")
        consented = request.POST.get("consent") == "on"

        errors = {}
        if password != password2:
            errors["password"] = "Passwords do not match."
        if not consented:
            errors["consent"] = "You must agree to the terms to continue."
        if User.objects.filter(email=email).exists():
            errors["email"] = "An account with this email already exists."

        if errors:
            return render(request, self.template_name, {"errors": errors, "email": email})

        from django.utils import timezone
        user = User.objects.create_user(
            email=email,
            password=password,
            user_type=User.EMPLOYER,
            consented_to_terms=True,
            consented_at=timezone.now(),
        )
        login(request, user)
        return redirect("accounts:employer_register_step2")


class EmployerRegisterStep2View(View):
    template_name = "public/register_step2_employer.html"

    def get(self, request):
        if not request.user.is_authenticated or not request.user.is_employer:
            return redirect("accounts:employer_login")
        return render(request, self.template_name)

    def post(self, request):
        from apps.employers.models import Company, EmployerProfile
        from django.utils.text import slugify
        import uuid

        company_name = request.POST.get("company_name", "")
        base_slug    = slugify(company_name)
        slug         = base_slug if not Company.objects.filter(slug=base_slug).exists() \
                       else f"{base_slug}-{uuid.uuid4().hex[:6]}"

        company = Company.objects.create(name=company_name, slug=slug)
        EmployerProfile.objects.create(
            user              = request.user,
            company           = company,
            first_name        = request.POST.get("first_name", ""),
            last_name         = request.POST.get("last_name", ""),
            sex               = request.POST.get("sex", ""),
            birthday          = request.POST.get("birthday") or None,
            phone             = request.POST.get("phone", ""),
            house_unit        = request.POST.get("house_unit", ""),
            street_barangay   = request.POST.get("street_barangay", ""),
            city_municipality = request.POST.get("city_municipality", ""),
            province          = request.POST.get("province", ""),
        )
        return redirect("employers:dashboard")


class ClaimAccountView(View):
    """PESO import: user clicks their unique link to activate a stub account."""
    template_name = "public/claim_account.html"

    def get(self, request, token):
        try:
            user = User.objects.get(claim_token=token, is_claimed=False)
        except User.DoesNotExist:
            return render(request, self.template_name, {"error": "invalid_token"})
        return render(request, self.template_name, {"token": token})

    def post(self, request, token):
        try:
            user = User.objects.get(claim_token=token, is_claimed=False)
        except User.DoesNotExist:
            return render(request, self.template_name, {"error": "invalid_token"})

        password  = request.POST.get("password", "")
        password2 = request.POST.get("confirm_password", "")
        if password != password2:
            return render(request, self.template_name, {"error": "password_mismatch", "token": token})

        user.set_password(password)
        user.is_claimed = True
        user.claim_token = None
        user.save()
        login(request, user)

        if user.is_jobseeker:
            return redirect("jobseekers:resume")
        return redirect("employers:dashboard")


def logout_view(request):
    logout(request)
    return redirect("accounts:login")
