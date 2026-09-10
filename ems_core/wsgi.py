"""
WSGI config for ems_core project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ems_core.settings')

application = get_wsgi_application()

# If running on Vercel / serverless, ensure database schema is applied
if 'VERCEL' in os.environ or os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
    try:
        from django.core.management import call_command
        call_command('migrate', interactive=False)
    except Exception as mig_e:
        print(f"Migration error: {mig_e}")

app = application

