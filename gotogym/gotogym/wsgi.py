"""
WSGI config for gotogym project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.conf import settings
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gotogym.settings')


application = get_wsgi_application()

if not getattr(settings, 'DEBUG', False) and os.environ.get('GOTOGYM_SKIP_STARTUP_MIGRATIONS') != '1':
    call_command('migrate', interactive=False, verbosity=1)
