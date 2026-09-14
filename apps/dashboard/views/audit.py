from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required(login_url='login')
def audit_logs_view(request):
    return redirect('dashboard-database')

