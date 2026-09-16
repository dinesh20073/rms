from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.conf import settings
from urllib.parse import urlparse
import re

class RewriteHostPreserveMiddleware(MiddlewareMixin):
    """
    Middleware to ensure proxy rewrites from Vercel A (nizhalcommunity.in)
    to Vercel B (admin.nizhalcommunity.in) never force users to the admin domain.

    Responsibilities:
    1. Normalize HTTP_X_FORWARDED_HOST:
       - For any public customer-facing routes (/register/, /pay/, /pass/, /status/),
         treat the host as 'nizhalcommunity.in' regardless of whether the proxy forwards
         the original host header, has multiple comma-separated hosts, or is accessed directly.
       - Clean multi-valued X-Forwarded-Host headers.
    2. Intercept any redirects (301, 302, 303, 307, 308):
       - If a redirect's Location contains admin.nizhalcommunity.in (or vercel.app),
         and points to a public path (/register/, /pay/, /pass/, /status/), rewrite it to
         https://nizhalcommunity.in preserving the exact target path and query params.
       - If a redirect on a public path attempts to send the user to login or root admin,
         send them to https://nizhalcommunity.in/ (the public site).
       - Ensure relative redirects remain intact so the client's browser maintains its domain.
    3. 404 Protection:
       - Ensure missing static/media assets (including /register/static/) return 404,
         NOT an HTML redirect to the homepage.
    4. Ensure CORS headers are present on static assets, media, and API requests.
    """

    PUBLIC_PATH_PREFIXES = (
        '/register/',
        '/register',
        '/pay/',
        '/pay',
        '/pass/',
        '/pass',
        '/status/',
        '/status',
    )

    PUBLIC_HOSTNAME = 'nizhalcommunity.in'
    PUBLIC_BASE_URL = 'https://nizhalcommunity.in'

    def process_request(self, request):
        path = request.path_info or request.path

        # 1. Normalize X-Forwarded-Host if comma-separated (e.g. "nizhalcommunity.in, admin.nizhalcommunity.in")
        fwd_host = request.META.get('HTTP_X_FORWARDED_HOST', '')
        if fwd_host:
            hosts = [h.strip().lower() for h in fwd_host.split(',') if h.strip()]
            if 'nizhalcommunity.in' in hosts:
                request.META['HTTP_X_FORWARDED_HOST'] = self.PUBLIC_HOSTNAME
            elif hosts:
                request.META['HTTP_X_FORWARDED_HOST'] = hosts[0]

        # 2. For ANY public registration/pay/pass/status route, ensure the host is ALWAYS nizhalcommunity.in
        # This guarantees that request.get_host() and request.build_absolute_uri() always generate
        # nizhalcommunity.in, preventing accidental leakage or redirects to admin.nizhalcommunity.in.
        if any(path.startswith(prefix) for prefix in self.PUBLIC_PATH_PREFIXES):
            request.META['HTTP_X_FORWARDED_HOST'] = self.PUBLIC_HOSTNAME
            request.META['HTTP_HOST'] = self.PUBLIC_HOSTNAME
        else:
            referer = request.META.get('HTTP_REFERER', '').lower()
            if 'nizhalcommunity.in' in referer and 'admin.nizhalcommunity.in' not in referer:
                request.META['HTTP_X_FORWARDED_HOST'] = self.PUBLIC_HOSTNAME

        return None

    def process_response(self, request, response):
        path = request.path_info or request.path
        host = request.get_host().lower()
        is_admin_host = (
            'admin.nizhalcommunity.in' in host
            or 'admin-nizhal-community' in host
            or host.startswith('admin.')
        )

        # 1. Handle redirects
        if response.status_code in (301, 302, 303, 307, 308) and response.has_header('Location'):
            location = response['Location']
            parsed = urlparse(location)
            loc_path = parsed.path
            loc_netloc = parsed.netloc.lower()

            is_loc_admin = any(h in loc_netloc for h in ['admin.nizhalcommunity.in', 'admin-nizhal-community'])
            is_public_target = any(loc_path.startswith(prefix) for prefix in self.PUBLIC_PATH_PREFIXES)
            is_public_source = any(path.startswith(prefix) for prefix in self.PUBLIC_PATH_PREFIXES)

            if is_public_target or is_public_source:
                # If redirect points to login or admin dashboard or bare root:
                if loc_path in ('', '/', '/login', '/login/', '/admin', '/admin/', '/dashboard', '/dashboard/'):
                    response['Location'] = f"{self.PUBLIC_BASE_URL}/"
                elif is_loc_admin:
                    # Rewrite admin host to nizhalcommunity.in while preserving path & query
                    query_str = f"?{parsed.query}" if parsed.query else ""
                    response['Location'] = f"{self.PUBLIC_BASE_URL}{loc_path}{query_str}"
            elif is_admin_host:
                # If visitor is on the admin domain (e.g. www.admin.nizhalcommunity.in),
                # preserve their exact admin host in any redirect
                if location.startswith(('http://', 'https://')):
                    if 'www.admin.nizhalcommunity.in' in host and 'https://admin.nizhalcommunity.in' in location:
                        response['Location'] = location.replace('https://admin.nizhalcommunity.in', f"{request.scheme}://{host}")
            else:
                # When visitor is on the public customer site (nizhalcommunity.in):
                # Ensure no absolute redirect leaks admin domain
                if is_loc_admin:
                    query_str = f"?{parsed.query}" if parsed.query else ""
                    response['Location'] = f"{self.PUBLIC_BASE_URL}{loc_path}{query_str}"

        # 2. Redirect 404s safely:
        # Never redirect asset files (images, css, js, fonts) to HTML
        is_asset = (
            path.startswith(('/static/', '/media/', '/api/', '/register/static/', '/register/media/'))
            or any(path.endswith(ext) for ext in ('.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.webp', '.map'))
        )
        if response.status_code == 404 and not is_asset:
            if any(path.startswith(prefix) for prefix in self.PUBLIC_PATH_PREFIXES):
                return redirect(f"{self.PUBLIC_BASE_URL}/")
            if is_admin_host and path.startswith(('/dashboard', '/admin', '/login')):
                return redirect(f"{request.scheme}://{host}/")
            return redirect(f"{self.PUBLIC_BASE_URL}/")

        # 3. Add CORS headers for static assets, media, and API
        if path.startswith(('/static/', '/media/', '/api/', '/register/static/', '/register/media/')):
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, HEAD'
            response['Access-Control-Allow-Headers'] = '*'

        return response

