import time
from django.shortcuts import redirect
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import logout
from apps.audit.services import log_audit_event

# 15 minutes idle timeout (in seconds)
SESSION_IDLE_TIMEOUT = 900

class BankSessionSecurityMiddleware(MiddlewareMixin):
    """
    Bank-Level Session Security Middleware:
    1. Enforces strict no-cache headers on all dashboard/admin routes to prevent back-button caching.
    2. Enforces idle session expiration across requests.
    3. Handles AJAX/HTMX session expiration gracefully with HX-Redirect.
    """

    def process_request(self, request):
        path = request.path

        # Only enforce on dashboard and private routes
        is_dashboard_path = path.startswith('/dashboard/')
        is_login_path = path in ['/login/', '/dashboard/login/']

        if request.user.is_authenticated:
            # Check Idle Timeout
            now = int(time.time())
            last_activity = request.session.get('last_activity', now)
            
            # If idle too long (15 minutes), expire session
            if (now - last_activity) > SESSION_IDLE_TIMEOUT:
                username = request.user.username
                logout(request)
                request.session.flush()
                
                log_audit_event(
                    action='AUTH_SESSION_EXPIRED_IDLE',
                    reference_id=username,
                    details={'idle_seconds': (now - last_activity)},
                    actor=username,
                    ip_address=request.META.get('REMOTE_ADDR')
                )

                if request.headers.get('HX-Request') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    response = JsonResponse({'authenticated': False, 'redirect': '/login/?timeout=1'}, status=401)
                    response['HX-Redirect'] = '/login/?timeout=1'
                    return response

                return redirect('/login/?timeout=1')

            # Update last activity
            request.session['last_activity'] = now

        elif is_dashboard_path and not is_login_path and not path.startswith('/dashboard/session/'):
            # Unauthenticated access to dashboard
            if request.headers.get('HX-Request') or request.headers.get('x-requested-with') == 'XMLHttpRequest':
                response = JsonResponse({'authenticated': False, 'redirect': f'/login/?next={path}'}, status=401)
                response['HX-Redirect'] = f'/login/?next={path}'
                return response

        return None

    def process_response(self, request, response):
        path = request.path

        # Apply strict anti-caching headers on all authenticated or dashboard/login routes
        if path.startswith('/dashboard/') or path.startswith('/login/') or (hasattr(request, 'user') and request.user.is_authenticated):
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'

        return response
