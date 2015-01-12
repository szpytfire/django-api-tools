from django_api_tools.APIView import APIView
from django_api_tools.tests.models import Foo, Qux, TestProfile

__author__ = 'szpytfire'


class TestAPIView(APIView):
    registered_endpoints = {
        'profile': TestProfile,
        'foo': Foo,
        'qux': Qux
    }

    public_create_endpoints = (TestProfile, )

    return_on_login = 'user.test_profile'