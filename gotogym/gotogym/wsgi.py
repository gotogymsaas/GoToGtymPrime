"""
WSGI config for gotogym project.

It exposes the WSGI callable as a module-level variable named ``application``.

Las migraciones no se aplican aqui: en Azure las corre el Startup Command del
App Service (`migrate && collectstatic && gunicorn`) una sola vez, antes de
que arranquen los workers. Hacerlo tambien al importar este modulo las
ejecutaba de nuevo en cada worker.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gotogym.settings')

application = get_wsgi_application()
