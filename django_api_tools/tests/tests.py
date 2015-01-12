import json

from django_api_tools.APIModel import APIModel, UserAuthCode
from django_api_tools.APIView import APIUrl, ReservedURL, StatusCode
from django_api_tools.tests.models import Foo, Bar, Baz, Qux, TestProfile
from django_api_tools.tests.views import TestAPIView

from django.test import TestCase
from django.test.client import RequestFactory, Client
from django.contrib.auth.models import AnonymousUser, User
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.core.exceptions import ObjectDoesNotExist

__author__ = 'szpytfire'


class APIToolsTestCase(TestCase):

    def assertDictKeysEqual(self, dict, keys):
        # For related fields, APIModel cuts off the special related syntax when dictifying
        # We should therefore do the same when testing for the correct keys

        for index, val in enumerate(keys):
            prefix = filter(lambda prefix: val.startswith(prefix), APIModel._reserved_prefixes)
            if prefix:
                keys[index] = keys[index][len(prefix[0]) + 1:]

        self.assertSetEqual(set(dict.keys()), set(keys))

class APIModelTestCase(APIToolsTestCase):

    fixtures = ['user_testprofile_foo.json', 'bar_baz_qux.json']

    def remove_foreign_key_fields(self, fields):
        return [field for field in fields if not filter(lambda prefix: field.startswith(prefix), APIModel._reserved_prefixes)]

    def test_dictify(self):
        foo = Foo.objects.get(id=1)
        foo._curr_user = AnonymousUser()
        # Test no fields to include returns empty dict
        self.assertDictEqual(foo.dictify([], False), {})

        # Test random fields to include returns empty dict
        self.assertDictEqual(foo.dictify(['bar1', 'bar2'], False), {})

        # Test defaults to public user
        self.assertDictKeysEqual(foo.dictify(Foo.long_description_fields, False), list(Foo.public_fields))

        # Test correct registered user fields returned
        foo._user_auth = UserAuthCode.REGISTERED_USER
        self.assertDictKeysEqual(foo.dictify(Foo.long_description_fields, False), list(Foo.public_fields + Foo.registered_user_fields))

        # Test correct owner fields returned
        foo._user_auth = UserAuthCode.OWNER
        self.assertDictKeysEqual(foo.dictify(Foo.long_description_fields, False), list(Foo.public_fields + Foo.registered_user_fields + Foo.owner_only_fields))

    def test_dictify_helper(self):
        user = User.objects.get(id=1)

        foo = Foo.objects.get(id=1)
        foo.set_user_auth(user)
        # Test no dictified fields returned for empty fields to return
        self.assertDictEqual(foo.dictify_helper(Foo.public_fields, [], False), {})

        # Test no dictified fields returned for fields which aren't in the auth level
        self.assertDictEqual(foo.dictify_helper(Foo.public_fields, ['bar1', 'bar2'], False), {})

        # Test regular field is set in the dictionary
        dictified_foo = foo.dictify_helper(Foo.public_fields, Foo.public_fields, False)
        self.assertEqual(dictified_foo['id'], foo.id)

        # Test invalid regular fields is set as None
        non_existent_field = ('test', )
        dictified_foo = foo.dictify_helper(non_existent_field, non_existent_field, False)
        self.assertIsNone(dictified_foo[non_existent_field[0]])

        # Test invalid related field is set as None
        non_existent_rel_field = ('fk_short_test', )
        dictified_foo = foo.dictify_helper(non_existent_rel_field, non_existent_rel_field, False)
        self.assertIsNone(dictified_foo['test'])

        # Test fk_short only returns the foreign model's ID
        fk_short_field = ('fk_short_baz', )
        bar = Bar.objects.get(id=1)
        bar.set_user_auth(user)
        dictified_bar = bar.dictify_helper(fk_short_field, fk_short_field, False)
        self.assertEqual(len(dictified_bar), 1)
        self.assertDictKeysEqual(dictified_bar['baz'], self.remove_foreign_key_fields(bar.baz.short_description_fields))

        # Test fk_long returns the foreign model's dictify_long()
        fk_long_field = ('fk_long_baz', )
        dictified_bar = bar.dictify_helper(fk_long_field, fk_long_field, False)
        self.assertEqual(len(dictified_bar), 1)
        self.assertDictKeysEqual(dictified_bar['baz'], self.remove_foreign_key_fields(bar.baz.short_description_fields + bar.baz.long_description_fields))

        # Test onetoone_short only returns the foreign model's ID
        onetoone_short_field = ('onetoone_short_owner', )
        dictified_foo = foo.dictify_helper(onetoone_short_field, onetoone_short_field, False)
        self.assertEqual(len(dictified_foo), 1)
        self.assertDictKeysEqual(dictified_foo['owner'], self.remove_foreign_key_fields(foo.owner.short_description_fields))

        # Test onetoone_long returns the foreign model's dictify_long()
        fk_long_field = ('onetoone_long_owner', )
        qux = Qux.objects.get(id=1)
        qux.set_user_auth(user)
        dictified_qux = qux.dictify_helper(fk_long_field, fk_long_field, False)
        self.assertEqual(len(dictified_qux), 1)
        self.assertDictKeysEqual(dictified_qux['owner'], self.remove_foreign_key_fields(qux.owner.short_description_fields + qux.owner.long_description_fields))

        # Test rel_short only returns the related models' ID's
        rel_short_field = ('rel_short_bars', )
        baz = Baz.objects.get(id=1)
        baz.set_user_auth(user)
        dictified_baz = baz.dictify_helper(rel_short_field, rel_short_field, False)
        self.assertEqual(len(dictified_baz), 1)
        self.assertEqual(len(dictified_baz['bars']), baz.bars.all().count())
        self.assertDictKeysEqual(dictified_baz['bars'][0], self.remove_foreign_key_fields(baz.bars.all()[0].short_description_fields))

        # Test rel_long returns the related models' dictify_long()
        rel_long_field = ('rel_long_bars', )
        dictified_baz = baz.dictify_helper(rel_long_field, rel_long_field, False)
        self.assertEqual(len(dictified_baz), 1)
        self.assertEqual(len(dictified_baz['bars']), baz.bars.all().count())
        self.assertDictKeysEqual(dictified_baz['bars'][0], self.remove_foreign_key_fields(baz.bars.all()[0].short_description_fields + baz.bars.all()[0].long_description_fields))

        # Test m2m_short only returns the related models' ID's
        m2m_short_field = ('m2m_short_foos', )
        qux = Qux.objects.get(id=1)
        qux.set_user_auth(user)
        qux.foos.add(foo)

        dictified_qux = qux.dictify_helper(m2m_short_field, m2m_short_field, False)
        self.assertEqual(len(dictified_qux), 1)
        self.assertEqual(len(dictified_qux['foos']), qux.foos.all().count())
        self.assertDictKeysEqual(dictified_qux['foos'][0], self.remove_foreign_key_fields(qux.foos.all()[0].short_description_fields))

        # Test m2m_long returns the related models' dictify_long()
        m2m_long_field = ('m2m_long_foos', )
        dictified_qux = qux.dictify_helper(m2m_long_field, m2m_long_field, False)
        self.assertEqual(len(dictified_qux), 1)
        self.assertEqual(len(dictified_qux['foos']), qux.foos.all().count())
        self.assertDictKeysEqual(dictified_qux['foos'][0], self.remove_foreign_key_fields(qux.foos.all()[0].short_description_fields + qux.foos.all()[0].long_description_fields))

    def test_dictify_short(self):
        # Test that the method only returns the short description fields
        foo = Foo.objects.get(id=1)
        self.assertDictKeysEqual(foo.dictify_short(False), Foo.short_description_fields)

    def test_dictify_long(self):
        # Test that the method returns the long and short description fields
        foo = Foo.objects.get(id=1)
        owner = TestProfile.objects.get(id=1).user
        foo.set_user_auth(owner)
        self.assertDictKeysEqual(foo.dictify_long(False), list(Foo.short_description_fields + Foo.long_description_fields))

    def test_dictify_with_auth(self):
        active_foo = Foo.objects.get(id=1)
        deactivated_foo = Foo.objects.filter(active=0)[0]

        owner = User.objects.get(id=1)
        not_owner = User.objects.get(id=2)
        public_user = AnonymousUser()

        # Test whether a deactivated instance returns None
        self.assertIsNone(deactivated_foo.dictify_with_auth(owner, False))

        # Test whether a public user only sees the public fields
        self.assertDictKeysEqual(active_foo.dictify_with_auth(public_user, False), list(Foo.public_fields))

        # Test whether an owner can view all the fields
        self.assertDictKeysEqual(active_foo.dictify_with_auth(owner, False), list(Foo.public_fields + Foo.registered_user_fields + Foo.owner_only_fields))

        # Test whether a registered user sees registered user + public fields
        self.assertDictKeysEqual(active_foo.dictify_with_auth(not_owner, False), list(Foo.public_fields + Foo.registered_user_fields))

    def test_is_owner(self):
        # Test ownership of Foo
        foo = Foo.objects.get(id=1)

        # Test Foo with its rightful owner
        # Test Foo with its rightful owner
        owner = User.objects.get(id=1)
        self.assertTrue(foo.is_owner(owner))

        # Test Foo with an incorrect owner
        not_owner = User.objects.get(id=2)
        self.assertFalse(foo.is_owner(not_owner))

        # Test Bar with an arbitrary user - Bar's don't have an owner.
        bar = Bar.objects.get(id=1)
        self.assertTrue(bar.is_owner(owner))

    def test_get_all(self):
        user = User.objects.get(id=1)
        # Test number of Foo's equal to 10
        self.assertEqual(len(Foo.get_all(1, user)), Foo.pagination)

        # Test number of Bar's equal to number of Bar's (< 10)
        self.assertEqual(len(Bar.get_all(1, user)), Bar.objects.all().count())

        # Test invalid page number raises expected exception
        with self.assertRaises(EmptyPage):
            Bar.get_all(2, user)

        # Test invalid page value raises expected exception
        with self.assertRaises(PageNotAnInteger):
            Bar.get_all("foo", user)

    def test_get_model_instance(self):
        # Test getting a Foo object with a valid ID
        valid_foo_id = 1

        # Make sure the method returns the right object
        foo = Foo.objects.get(id=valid_foo_id)
        self.assertEqual(Foo.get_model_instance(valid_foo_id), foo)

        # Test invalid lookup raises expected exception
        with self.assertRaises(ValueError):
            Foo.objects.get(id="foo")

        with self.assertRaises(ObjectDoesNotExist):
            Foo.objects.get(id=20)

class APIViewTestCase(APIToolsTestCase):

    fixtures = ['user_testprofile_foo.json', 'bar_baz_qux.json']
    urls = 'django_api_tools.tests.urls'

    def setUp(self):
        self.factory = RequestFactory()

    def test_get(self):
        t = TestAPIView()
        # Test invalid request gives back 404
        request = self.factory.get('/test_api/')
        response = t.get(request)
        self.assertEqual(response.status_code, StatusCode.NOT_FOUND)

        # Test reserved URL gives back 200
        request = self.factory.get('/test_api/{}'.format(ReservedURL.CSRFTOKEN))
        response = t.get(request)
        self.assertEqual(response.status_code, StatusCode.OK)

        user = User.objects.get(id=1)

        # Test model request returns 200
        request = self.factory.get('/test_api/foo/')
        request.user = user
        response = t.get(request)
        self.assertEqual(response.status_code, StatusCode.OK)

        # Test get instance gives back 200
        request = self.factory.get('/test_api/foo/1/')
        request.user = user
        response = t.get(request)
        self.assertEqual(response.status_code, StatusCode.OK)

        # Test custom request on model with custom_request implemented gives back 200
        request = self.factory.get('/test_api/qux/1/custom/')
        request.user = user
        response = t.get(request)
        self.assertEqual(response.status_code, StatusCode.OK)

        # Test custom request on model without implementation gives back 404
        request = self.factory.get('/test_api/foo/1/custom/')
        request.user = user
        response = t.get(request)
        self.assertEqual(response.status_code, StatusCode.NOT_FOUND)

    def test_post(self):
        t = TestAPIView()

        # Test invalid request gives back 404
        request = self.factory.post('/test_api/')
        response = t.post(request)
        self.assertEqual(response.status_code, StatusCode.NOT_FOUND)

        # Test reserved URL gives back 200
        request = self.factory.post('/test_api/{}/'.format(ReservedURL.CSRFTOKEN))
        response = t.post(request)
        self.assertEqual(response.status_code, StatusCode.OK)

        user = User.objects.get(id=1)

        # Test post model request (create) returns 200
        APIUrl.ADDITIONAL_FIELDS = list()
        request = self.factory.post('/test_api/foo/', data={"f2": "foo"})
        request.user = user
        response = t.post(request)
        self.assertEqual(response.status_code, StatusCode.OK)

        # Test post instance  (update) gives back 200
        APIUrl.ADDITIONAL_FIELDS = list()
        foo = Foo.objects.get(id=1)
        request = self.factory.post('/test_api/foo/{}/'.format(foo.id), data={"f1": True})
        request.user = user
        response = t.post(request)
        self.assertEqual(response.status_code, StatusCode.OK)

    def test_get_all(self):
        user = User.objects.get(id=1)
        t = TestAPIView()

        # Test get first page of Foo's gives back 10 results
        request = self.factory.get('/test_api/foo/')
        request.user = user
        t._endpoint_model = Foo
        response = t._get_all(request)
        self.assertEqual(len(json.loads(response.content)), 10)

        # Test second page of Foo's gives back 1 results
        request = self.factory.get('/test_api/foo/', data={"page": 2})
        request.user = user
        t._endpoint_model = Foo
        response = t._get_all(request)
        self.assertEqual(len(json.loads(response.content)), 1)

        # Test third page of Foo's gives back 404
        request = self.factory.get('/test_api/foo/', data={"page": 3})
        request.user = user
        t._endpoint_model = Foo
        response = t._get_all(request)
        self.assertIsNone(json.loads(response.content))

    def test_get_instance(self):
        user = User.objects.get(id=1)
        t = TestAPIView()

        # Test Foo ID = 1 gives back 200/ correct Foo
        foo = Foo.objects.get(id=1)
        foo_dict = foo.dictify_with_auth(user, short_dict=False)
        request = self.factory.get('/test_api/foo/{}/'.format(foo.id))
        request.user = user
        t._endpoint_model = Foo
        t._url_validator = APIUrl(request)
        response = t._get_instance(request)
        self.assertDictEqual(json.loads(response.content), foo_dict)
        self.assertEqual(response.status_code, StatusCode.OK)

        # Test Foo ID = 22 gives back 404/ none
        request = self.factory.get('/test_api/foo/22/')
        request.user = user
        t._endpoint_model = Foo
        t._url_validator = APIUrl(request)
        response = t._get_instance(request)
        self.assertEqual(response.status_code, StatusCode.NOT_FOUND)
        self.assertIsNone(json.loads(response.content))

        # Test Foo ID = "foo" gives back 404
        request = self.factory.get('/test_api/foo/foo/')
        request.user = user
        t._endpoint_model = Foo
        t._url_validator = APIUrl(request)
        response = t._get_instance(request)
        self.assertEqual(response.status_code, StatusCode.NOT_FOUND)
        self.assertIsNone(json.loads(response.content))

        # Test Qux /custom/ gives back 200/ correct value
        request = self.factory.get('/test_api/qux/custom/')
        request.user = user
        t._endpoint_model = Qux
        t._url_validator = APIUrl(request)
        response = t._get_instance(request)
        self.assertEqual(response.status_code, StatusCode.OK)
        self.assertEqual(json.loads(response.content), Qux.api_custom_request(request))

    def test_post_handler(self):
        t = TestAPIView()

        # Test non-authenticated user and private endpoint gives back 404
        request = self.factory.post('/test_api/qux/')
        request.user = AnonymousUser()
        public_endpoints = (Foo, )
        t._endpoint_model = Qux
        response = t._post_handler(request, public_endpoints)
        self.assertEqual(response.status_code, StatusCode.NOT_FOUND)

        # Test create:
        f2_val = "hello"
        user = User.objects.get(id=1)
        request = self.factory.post('/test_api/foo/', data={"f2": f2_val})
        request.user = user
        public_endpoints = (Qux, )
        t._endpoint_model = Foo
        response = t._post_handler(request, public_endpoints)
        foo_dict = json.loads(response.content)
        self.assertEqual(response.status_code, StatusCode.OK)
        self.assertEqual(foo_dict['f2'], f2_val)
        self.assertEqual(foo_dict, Foo.objects.get(id=foo_dict['id']).dictify_with_auth(user, short_dict=False))

        # Test create Foo with bad/missing fields returns 404
        f1_val = "hello"
        request = self.factory.post('/test_api/foo/', data={"f1": f1_val})
        request.user = user
        response = t._post_handler(request, public_endpoints)
        self.assertEqual(response.status_code, StatusCode.NOT_FOUND)

        # Test update with owner returns 200 + updated foo object
        foo = Foo.objects.get(id=1)
        f1_before = foo.f1
        foo1_url = '/test_api/foo/{}/'.format(foo.id)
        request = self.factory.post(foo1_url, data={"f1": True})
        request.user = user
        t._url_validator = APIUrl(request)
        response = t._post_handler(request, public_endpoints, create=False)
        self.assertEqual(response.status_code, StatusCode.OK)
        response_content = json.loads(response.content)
        self.assertEqual(response_content['f1'], f1_before + 1)
        new_foo = Foo.objects.get(id=1)
        self.assertDictEqual(new_foo.dictify_with_auth(user, False), response_content)

        # Test update with non owner returns 404
        request = self.factory.post(foo1_url, data={"f1": True})
        request.user = AnonymousUser()
        response = t._post_handler(request, public_endpoints, create=False)
        self.assertEqual(response.status_code, StatusCode.NOT_FOUND)

        # Test deactivate gives back 404 + Test that the deactivate date is set
        request = self.factory.post(foo1_url, data={"deactivate": True})
        request.user = user
        response = t._post_handler(request, public_endpoints, create=False)
        self.assertEqual(response.status_code, StatusCode.NOT_FOUND)

    def test_get_json_response_for_instance(self):
        foo = Foo.objects.get(id=1)
        t = TestAPIView()

        # Test Anonymous user gives back public fields
        user = AnonymousUser()
        response_content = t.get_json_response_for_instance(foo, user).content
        self.assertDictKeysEqual(json.loads(response_content), Foo.public_fields)

        # Test registered user gives back all fields
        user = User.objects.get(id=2)
        response_content = t.get_json_response_for_instance(foo, user).content
        self.assertDictKeysEqual(json.loads(response_content), list(Foo.public_fields + Foo.registered_user_fields))

        # Test owner gives back all fields
        user = User.objects.get(id=1)
        response_content = t.get_json_response_for_instance(foo, user).content
        self.assertDictKeysEqual(json.loads(response_content), list(Foo.public_fields + Foo.registered_user_fields + Foo.owner_only_fields))


    def test_validate_request(self):
        t = TestAPIView()

        # Test invalid request returns False
        request = self.factory.get('/test_api/fob/')
        self.assertFalse(t._validate_request(request))

        request = self.factory.get('/test_api/123/123/123/')
        self.assertFalse(t._validate_request(request))

        # Test valid request returns True
        request = self.factory.get('/test_api/foo/')
        self.assertTrue(t._validate_request(request))

        # Test reserved URL returns True
        request = self.factory.get('/test_api/{}/'.format(ReservedURL.LOGIN))
        self.assertTrue(t._validate_request(request))

    def test_handle_login_logout_request(self):
        # We need to use Django's Client to test the login
        # as RequestFactory doesn't offer any middleware by default
        c = Client()
        login_url = "/test_api/{}/".format(ReservedURL.LOGIN)
        # Test valid user login returns the user's profile + sets cookies
        valid_user = User.objects.get(id=1)
        new_password = "newpassword1"
        valid_user.set_password(new_password)
        valid_user.save()
        response = c.post(login_url, data={"username": valid_user.username, "password": new_password})
        self.assertEqual(response.status_code, StatusCode.OK)
        self.assertDictEqual(json.loads(response.content), valid_user.test_profile.dictify_with_auth(valid_user, short_dict=False))

        # Test that logout deletes the authenticated session
        session_val_before = response.cookies['sessionid'].value
        response = c.post("/test_api/{}/".format(ReservedURL.LOGOUT))
        session_val_after = response.cookies['sessionid'].value
        self.assertNotEqual(session_val_before, session_val_after)

        # Test an invalid login returns 404
        response = c.post(login_url, data={"username": valid_user.username, "password": "badpassword"})
        self.assertEqual(response.status_code, StatusCode.NOT_FOUND)

        # Test inactive user login returns 404
        valid_user.is_active = False
        valid_user.save()
        response = c.post(login_url, data={"username": valid_user.username, "password": new_password})
        self.assertEqual(response.status_code, StatusCode.NOT_FOUND)

    def test_handle_csrf_request(self):
        # Test csrf request sets a token
        c = Client()
        response = c.get("/test_api/{}".format(ReservedURL.CSRFTOKEN))
        self.assertIsNotNone(response.cookies['csrftoken'].value)

    def test_handle_custom_request(self):
        t = TestAPIView()

        # Test model which handles custom request returns 200
        request = self.factory.get('/test_api/qux/custom/')
        t._endpoint_model = Qux
        response = t.handle_custom_request(request)
        self.assertEqual(response.status_code, StatusCode.OK)

        # Test model which doesn't handle custom request returns 404
        request = self.factory.get('/test_api/foo/custom/')
        t._endpoint_model = Foo
        response = t.handle_custom_request(request)
        self.assertEqual(response.status_code, StatusCode.NOT_FOUND)

class APIUrlTestCase(APIToolsTestCase):

    def setUp(self):
        self.factory = RequestFactory()

    def test_split_url_components(self):
        # Test an invalid request
        request = self.factory.get("/api/")
        splitter = APIUrl(request)
        self.assertFalse(splitter.is_valid_request())

        # Test a model request
        MODEL_NAME = "foo"
        request = self.factory.get("/api/{}/".format(MODEL_NAME))
        splitter = APIUrl(request)
        self.assertTrue(splitter.is_valid_request())
        self.assertTrue(splitter.is_model_request())
        self.assertEqual(MODEL_NAME, splitter.REQUESTED_MODEL)

        # Test a model instance request
        MODEL_INSTANCE = "1"
        request = self.factory.get("/api/{}/{}/".format(MODEL_NAME, MODEL_INSTANCE))
        splitter = APIUrl(request)
        self.assertTrue(splitter.is_valid_request())
        self.assertTrue(splitter.is_model_instance_request())
        self.assertEqual(MODEL_NAME, splitter.REQUESTED_MODEL)
        self.assertEqual(MODEL_INSTANCE, splitter.REQUESTED_MODEL_INSTANCE)

        # Test a reserved URL request
        reserved_url = ReservedURL.LOGOUT
        request = self.factory.get("/api/{}/".format(reserved_url))
        splitter = APIUrl(request)
        self.assertTrue(splitter.is_valid_request())
        self.assertTrue(splitter.is_reserved_url())
        self.assertEqual(reserved_url, splitter.RESERVED_URL)

        # Test a custom request
        reserved_url = ReservedURL.LOGOUT
        request = self.factory.get("/api/{}/".format(reserved_url))
        splitter = APIUrl(request)
        self.assertTrue(splitter.is_valid_request())
        self.assertTrue(splitter.is_reserved_url())
        self.assertEqual(reserved_url, splitter.RESERVED_URL)