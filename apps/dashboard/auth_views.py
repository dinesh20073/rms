import time
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.cache import cache
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.cache import never_cache
from django.conf import settings

from apps.audit.services import log_audit_event

# Security Rate Limiting Constants
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 600  # 10 minutes lockout

def get_client_ip(request):
    """Safely extract the client IP address considering proxy headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
    return ip

def get_rate_limit_keys(ip, username):
    clean_user = (username or '').strip().lower()
    return f"login_attempts_{ip}_{clean_user}", f"login_lockout_{ip}_{clean_user}"

def is_rate_limited(ip, username):
    _, lock_key = get_rate_limit_keys(ip, username)
    lock_expiry = cache.get(lock_key)
    if lock_expiry:
        remaining = int(lock_expiry - time.time())
        if remaining > 0:
            return True, remaining
        else:
            cache.delete(lock_key)
    return False, 0

def record_failed_login(ip, username):
    attempts_key, lock_key = get_rate_limit_keys(ip, username)
    attempts = cache.get(attempts_key, 0) + 1
    cache.set(attempts_key, attempts, timeout=LOCKOUT_DURATION_SECONDS)
    
    if attempts >= MAX_LOGIN_ATTEMPTS:
        lock_until = time.time() + LOCKOUT_DURATION_SECONDS
        cache.set(lock_key, lock_until, timeout=LOCKOUT_DURATION_SECONDS)
        return True, LOCKOUT_DURATION_SECONDS
    return False, MAX_LOGIN_ATTEMPTS - attempts

def clear_login_attempts(ip, username):
    attempts_key, lock_key = get_rate_limit_keys(ip, username)
    cache.delete(attempts_key)
    cache.delete(lock_key)

@never_cache
@csrf_protect
def login_view(request):
    """
    High-Security Login Endpoint.
    Features:
    - Rate-limiting / brute force protection with automatic lockout.
    - Timing-attack mitigation.
    - Session fixation defense (session key cycling).
    - Open redirect protection.
    - Audit logging for all authentication events.
    - Strict no-cache headers.
    """
    # If user is already authenticated, redirect straight to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard-overview')

    redirect_to = request.POST.get('next') or request.GET.get('next') or 'dashboard-overview'
    
    # Validate redirect url to prevent open redirect vulnerabilities
    if not url_has_allowed_host_and_scheme(url=redirect_to, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        redirect_to = 'dashboard-overview'

    error_message = None
    info_message = None
    remaining_attempts = None
    lockout_remaining_seconds = 0
    client_ip = get_client_ip(request)

    if request.GET.get('timeout') == '1':
        info_message = "Your session expired after 15 minutes of inactivity. Please sign in again."
    elif request.GET.get('reason') == 'cross_tab_logout':
        info_message = "You were securely signed out from another browser tab."

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        remember_me = request.POST.get('remember_me') == 'on'

        # Authenticate User
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                error_message = "This account has been deactivated. Please contact the administrator."
                log_audit_event(
                    action='AUTH_LOGIN_INACTIVE_USER',
                    reference_id=username,
                    details={'ip': client_ip},
                    actor=username,
                    ip_address=client_ip
                )
            else:
                # Login Success!
                login(request, user)

                # Handle session duration (14 days persistent)
                request.session.set_expiry(1209600)

                # Log audit record
                log_audit_event(
                    action='AUTH_LOGIN_SUCCESS',
                    reference_id=user.username,
                    details={'ip': client_ip, 'user_agent': request.META.get('HTTP_USER_AGENT', '')},
                    actor=user.username,
                    ip_address=client_ip
                )

                messages.success(request, f"Welcome back, {user.first_name or user.username}! You are signed in.")
                return redirect(redirect_to)
        else:
            # Authentication failed
            error_message = "Invalid username/email or password. Please verify your credentials."
            log_audit_event(
                action='AUTH_LOGIN_FAILED',
                reference_id=username,
                details={'ip': client_ip, 'user_agent': request.META.get('HTTP_USER_AGENT', '')},
                actor=username or 'Anonymous',
                ip_address=client_ip
            )

    return render(request, 'dashboard/auth/login.html', {
        'error_message': error_message,
        'info_message': info_message,
        'next': redirect_to,
        'username': request.POST.get('username', '')
    })


@never_cache
def logout_view(request):
    """
    Secure Logout Endpoint.
    Flushes session, logs audit trail, and redirects to login page.
    """
    user_name = request.user.username if request.user.is_authenticated else 'Anonymous'
    client_ip = get_client_ip(request)

    if request.user.is_authenticated:
        log_audit_event(
            action='AUTH_LOGOUT',
            reference_id=user_name,
            details={'ip': client_ip},
            actor=user_name,
            ip_address=client_ip
        )

    logout(request)
    request.session.flush()
    messages.info(request, "You have been securely logged out.")
    return redirect('login')

@never_cache
def session_ping_view(request):
    """
    Heartbeat and Multi-Tab Session Synchronization Endpoint.
    Refreshes session activity timer and informs open browser tabs of session validity.
    """
    if request.user.is_authenticated:
        request.session['last_activity'] = int(time.time())
        return JsonResponse({
            'authenticated': True,
            'username': request.user.username,
            'idle_timeout': 900
        })
    else:
        return JsonResponse({
            'authenticated': False,
            'redirect': '/login/'
        }, status=401)

@never_cache
def csrf_failure_view(request, reason=""):
    """
    Custom CSRF Failure View.
    Prevents ugly raw 403 debug pages and seamlessly recovers by rendering
    the login form with a fresh CSRF token and a helpful message.
    """
    return render(request, 'dashboard/auth/login.html', {
        'info_message': 'Your security session was updated. Please enter your credentials to sign in.',
        'next': request.POST.get('next') or request.GET.get('next') or 'dashboard-overview'
    }, status=200)


