from django.conf.urls import patterns, include, url
from django.views.decorators.csrf import ensure_csrf_cookie
from api_tools.tests.views import TestAPIView

from django.contrib import admin

__author__ = 'szpytfire'

admin.autodiscover()

urlpatterns = patterns('',
    url(r'^test_api/', ensure_csrf_cookie(TestAPIView.as_view())),
)