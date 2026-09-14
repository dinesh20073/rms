from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect

class BankSessionSecurityMiddleware(MiddlewareMixin):
    """
    Session & Security Headers Middleware:
    - Automatically redirects any customer-side URL (prefixed with admin.)
      to admin login (or dashboard if already authenticated).
    - Applies security headers to dashboard and authenticated routes.
    """

    EXEMPT_PREFIXES = (
        '/dashboard/',
        '/login/',
        '/logout/',
        '/admin/',
        '/api/',
        '/static/',
        '/media/',
        '/pay/',
        '/pass/',
        '/status/',
        '/favicon.ico',
    )

    def process_request(self, request):
        path = request.path
        host = request.get_host().lower()

        is_admin_host = (
            'admin.nizhalcommunity.in' in host
            or 'admin-nizhal-community' in host
            or host.startswith('admin.')
        )

        if is_admin_host:
            # If path does not start with an allowed admin or service prefix:
            if not any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
                if getattr(request, 'user', None) and request.user.is_authenticated:
                    return redirect('dashboard-overview')
                return redirect('login')

        return None

    def process_response(self, request, response):
        path = request.path
        if path.startswith('/dashboard/') or path.startswith('/login/'):
            response['Cache-Control'] = 'private, no-cache'
        return response
