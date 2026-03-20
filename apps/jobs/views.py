from django.shortcuts import render

def landing_jobseeker(request):
    return render(request, 'public/landing_jobseeker.html')