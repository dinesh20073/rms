from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
import re

class RewriteHostPreserveMiddleware(MiddlewareMixin):
    """
    Middleware to ensure proxy rewrites from Vercel A (nizhalcommunity.in)
    to Vercel B (admin.nizhalcommunity.in) never force users to the admin domain.

    Responsibilities:
    1. Normalize HTTP_X_FORWARDED_HOST when proxy headers contain multiple hosts
       or when requests arrive for public registration/payment/pass routes.
    2. Intercept any redirects (301, 302, 307, 308) and rewrite any Location header
       pointing to admin.nizhalcommunity.in back to nizhalcommunity.in (or relative path).
    3. Ensure CORS headers are present on static assets and API requests so that
       browsers loading the page via nizhalcommunity.in do not hit CORS blocks.
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

    def process_request(self, request):
        path = request.path_info or request.path

        # 1. Normalize X-Forwarded-Host if comma-separated (e.g. "nizhalcommunity.in, admin.nizhalcommunity.in")
        fwd_host = request.META.get('HTTP_X_FORWARDED_HOST', '')
        if fwd_host:
            hosts = [h.strip().lower() for h in fwd_host.split(',') if h.strip()]
            if 'nizhalcommunity.in' in hosts:
                request.META['HTTP_X_FORWARDED_HOST'] = 'nizhalcommunity.in'
            elif hosts:
                request.META['HTTP_X_FORWARDED_HOST'] = hosts[0]

        # 2. If the request is for public customer-facing routes and came with Referer or Proxy from nizhalcommunity.in:
        referer = request.META.get('HTTP_REFERER', '').lower()
        if any(path.startswith(prefix) for prefix in self.PUBLIC_PATH_PREFIXES):
            if 'nizhalcommunity.in' in referer and 'admin.nizhalcommunity.in' not in referer:
                request.META['HTTP_X_FORWARDED_HOST'] = 'nizhalcommunity.in'

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
            
            if is_admin_host:
                # If visitor is on the admin domain (e.g. www.admin.nizhalcommunity.in),
                # preserve their exact admin host in any redirect
                if location.startswith(('http://', 'https://')):
                    # If redirect is pointing to bare admin domain but user is on www.admin domain:
                    if 'www.admin.nizhalcommunity.in' in host and 'https://admin.nizhalcommunity.in' in location:
                        response['Location'] = location.replace('https://admin.nizhalcommunity.in', f"{request.scheme}://{host}")
            else:
                # When visitor is on the public customer site (nizhalcommunity.in):
                # Ensure no absolute redirect leaks admin domain
                if 'admin.nizhalcommunity.in' in location or 'admin-nizhal-community' in location:
                    new_location = re.sub(
                        r'^https?://(?:www\.admin\.nizhalcommunity\.in|admin\.nizhalcommunity\.in|admin-nizhal-community\.vercel\.app)',
                        'https://nizhalcommunity.in',
                        location
                    )
                    response['Location'] = new_location

                # For public registration/pay/pass/status paths, ensure no admin domain leak
                if any(path.startswith(prefix) for prefix in self.PUBLIC_PATH_PREFIXES):
                    if response['Location'].startswith(('http://', 'https://')):
                        if 'admin.nizhalcommunity.in' in response['Location']:
                            response['Location'] = re.sub(
                                r'^https?://[a-zA-Z0-9.-]*admin\.nizhalcommunity\.in',
                                'https://nizhalcommunity.in',
                                response['Location']
                            )

        # 2. Redirect any 404 on admin host to admin root URL (e.g. https://www.admin.nizhalcommunity.in/)
        if response.status_code == 404 and is_admin_host:
            if not path.startswith(('/static/', '/media/', '/api/')):
                return redirect(f"{request.scheme}://{host}/")

        # 3. Add CORS headers for static assets, media, and API
        if path.startswith(('/static/', '/media/', '/api/', '/register/static/')):
            response['Access-Control-Allow-Origin'] = '*'
            response['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, HEAD'
            response['Access-Control-Allow-Headers'] = '*'

        return response
