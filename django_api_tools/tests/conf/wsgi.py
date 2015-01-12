import os

from django.core.wsgi import get_wsgi_application

__author__ = 'szpytfire'


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_api_tools.tests.conf.settings")

application = get_wsgi_application()
