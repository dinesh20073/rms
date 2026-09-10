from django.utils.deprecation import MiddlewareMixin

class BankSessionSecurityMiddleware(MiddlewareMixin):
    """
    Session & Security Headers Middleware:
    Applies security headers to dashboard and authenticated routes.
    """

    def process_request(self, request):
        return None

    def process_response(self, request, response):
        path = request.path
        if path.startswith('/dashboard/') or path.startswith('/login/'):
            response['Cache-Control'] = 'private, no-cache'
        return response
