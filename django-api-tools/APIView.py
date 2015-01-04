import logging

from django.views.generic import View
from django.http import JsonResponse
from django.core.paginator import EmptyPage, PageNotAnInteger
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import authenticate, login, logout

__author__ = 'szpytfire'

logger = logging.getLogger(__name__)


class StatusCode(object):
    """
    Maintains verbose representations of HTTP status codes.
    """
    OK = 200
    NOT_FOUND = 404
    UNAUTHORIZED = 401

class ReservedURL(object):
    """
    Maintains a list of reserved API urls.
    """
    LOGIN = 'login'
    LOGOUT = 'logout'
    CSRFTOKEN = 'csrftoken'

    @classmethod
    def all(cls):
        """
        Get all the reserved API urls

        :return: reserved API urls
        """
        return (cls.LOGIN, cls.LOGOUT, cls.CSRFTOKEN)

class UnsafeJSONResponse(JsonResponse):
    """
    Subclass of JSONResponse which provides some default parameters:
    - Sets the Status code to 200
    - Sets the safe parameter to False, allowing non-dictionary objects to be returns as JSON
    """
    def __init__(self, data, status=StatusCode.OK):
        super(UnsafeJSONResponse, self).__init__(status=status, data=data, safe=False)

class BadJSONResponse(UnsafeJSONResponse):
    """
    Subclass of UnsafeJSONResponse which by default outputs no response on a bad request
    """
    def __init__(self, status, data=None):
      super(BadJSONResponse, self).__init__(status=status, data=data)

class APIUrl(object):
    """
    Provides URL validation.
    Splits the requesting URL into separate components and figures out what type
    of API call the request is.

    Extracts the endpoint model, model instance (if any), and custom request fields.
    Alternatively maps to a reserved URL.
    If no match is made, it deems the URL an invalid request.
    """

    # The endpoint model extracted from the request URL
    REQUESTED_MODEL = None
    # The endpoint model instance extracted from the request URL
    REQUESTED_MODEL_INSTANCE = None
    # Any fields extracted from the URL which are custom request fields
    ADDITIONAL_FIELDS = list()
    # The reserved URL matched to
    RESERVED_URL = None
    # A list of the reserved API urls
    RESERVED_URLS = ReservedURL.all()

    def __init__(self, request):
        """
        Splits the request URL on initialisation
        :param request: HTTP request object
        :return: None
        """
        self.split_url_components(request)

    def split_url_components(self, request):
        """
        Splits the URL into separate components for URL validation.

        We assume that API urls follow the structure:
        /api/<endpoint>/<instance_criteria>/<custom_field1>/<custom_field2>/....

        Where:
        - endpoint is the name of the model, or the custom name given to the model
        - instance_criteria is an id of an instance of the model or any other unique field
        - custom fields are handled by the specific model
        :param request: HTTP request object
        :return: None
        """


        url_components = request.path.split("/")

        # we start from position 2, as for a valid url,
        # the first component will be a '' empty string,
        # and the second component 'api'.
        for i in range(2, len(url_components)):
            if url_components[i] == '':
                continue

            # if the request is for a reserved URL, or an specifies an endpoint
            # model, this will be found at position 2
            if i == 2:
                # Check first if it's a reserved URL - if it is, there's no point
                # continuing with the looping process
                if url_components[i] in self.RESERVED_URLS:
                    self.RESERVED_URL = url_components[i]
                    break
                # if it's not a reserved url, it must be a requested model
                self.REQUESTED_MODEL = url_components[i]
            elif i == 3:
                self.REQUESTED_MODEL_INSTANCE = url_components[i]
            else:
                self.ADDITIONAL_FIELDS.append(url_components[i])

    def is_valid_request(self):
        """
        Returns whether or not the request was valid:
        - request either needs to have pointed to an endpoint or a reserved URL
        :return: Boolean depending on whether the URL request was valid
        """
        return self.REQUESTED_MODEL is not None or self.RESERVED_URL is not None

    def is_reserved_url(self):
        """
        Returns whether or not the request was for a reserved URL:
        :return: Boolean depending on whether the URL request was for a reserved URL
        """
        return self.RESERVED_URL

    def is_model_request(self):
        """
        Returns whether or not the request was an endpoint 'all' request:
        - request needs to have pointed to an endpoint but not an instance
        - and cannot have any additional/custom request fields
        :return: Boolean depending on whether the URL request was an endpoint 'all' request
        """
        return self.REQUESTED_MODEL and self.REQUESTED_MODEL_INSTANCE is None and not self.ADDITIONAL_FIELDS

    def is_model_instance_request(self):
        """
        Returns whether or not the request was a model instance request:
        - request needs to have pointed to an endpoint and an endpoint instance
        - but not have custom fields
        :return: Boolean depending on whether the URL request was an endpoint instance request
        """
        return self.REQUESTED_MODEL_INSTANCE and not self.ADDITIONAL_FIELDS

    def is_custom_request(self):
        """
        Returns whether or not the request was custom:
        :return: Boolean depending on whether the URL request was for a custom request
        """
        return bool(self.ADDITIONAL_FIELDS)


class APIView(View):
    """
    Class-Based view which provides generic handlers for GET/POST requests.
    """

    # Endpoints which the API allows access to
    registered_endpoints = {}
    # Endpoints which the API allows updating without user authentication
    public_update_endpoints = ()
    # Endpoints which the API allows creating without user authentication
    public_create_endpoints = ()

    # A string eval'd upon a successful login
    # This should contain a subclass of APIModel which can
    # be dictified and returned when a successful login occurs
    return_on_login = None

    def get(self, request, *args, **kwargs):
        """
        Provides a custom implementation for the standard get() method of a class based view
        :param request: the request object
        :param args:
        :param kwargs:
        :return: A JSONResponse object with a 200 status code if the request was valid,
        or 404 on an invalid request.
        """
        if not self._validate_request(request):
            return self.bad_request

        if self._url_validator.is_reserved_url():
            return self._handle_reserved_url_request(request)

        if self._url_validator.is_model_request():
            return self._get_all(request)

        if self._url_validator.is_model_instance_request():
            return self._get_instance(request)

        if self._url_validator.is_custom_request():
            return self.handle_custom_request(request)

        return self.bad_request

    def post(self, request, *args, **kwargs):
        """
        Provides a custom implementation for the standard post() method of a class based view
        :param request: the request object
        :param args:
        :param kwargs:
        :return: A JSONResponse object with a 200 status code if the request was valid,
        or 404 on an invalid request.
        """

        if not self._validate_request(request):
            return self.bad_request

        if self._url_validator.is_reserved_url():
            return self._handle_reserved_url_request(request)

        if self._url_validator.is_model_request():
            return self._post_handler(request, self.public_create_endpoints, create=True)

        if self._url_validator.is_model_instance_request():
            return self._post_handler(request, self.public_update_endpoints, create=False)


        # Currently no support for custom POST requests
        return self.bad_request

    def _get_all(self, request):
        """
        Handles a request to get all the instances of a model.
        Looks for a page number, or defaults to the first page if one isn't found.

        :param request: the request object containing a potential page parameter
        :return: Either a list of model instances, or a 404 if the page was invalid,
        or no objects exist for the page number provided.
        """
        page_number = request.GET.get('page', 1)

        try:
            model_dict = self._endpoint_model.get_all(page_number, request.user)
        except (EmptyPage, PageNotAnInteger), e:
            logger.info(e)
            return self.bad_request

        return self.valid_response(model_dict)

    def _get_instance(self, request):
        """
        Either retrieves the model instance requested, or upon failure
        treats the request as a custom request which is handled by the
        model.
        :param request: The request object
        :return: A dictionary representation of the model instance,
        the output of a custom request, or a 404 if both of these failed.
        """
        model_instance = self._retrieve_model_instance()

        if model_instance is None:
            return self.handle_custom_request(request)

        return self.get_json_response_for_instance(model_instance, request.user)

    def _retrieve_model_instance(self):
        """
        Wrapper for retrieving a model instance from the request URL
        :return: Either the model instance, or None if the request was invalid
        """
        try:
            model_instance = self._endpoint_model.get_model_instance(self._url_validator.REQUESTED_MODEL_INSTANCE)
            return model_instance
        except (ValueError, ObjectDoesNotExist), e:
            logger.info(e)

        return None

    def _post_handler(self, request, public_endpoints, create=True):
        """
        Handles both create and update POST requests.

        :param request: The request object
        :param public_endpoints: A list of endpoints that can be created/updated
        (depending on the request type) without user authentication
        :param create: Whether or not the request is a CREATE (False == update)
        :return: A json representation of the instance created/updated, or
        a 404 if the request was bad
        """
        if not request.user.is_authenticated() and self._endpoint_model not in public_endpoints:
            return self.bad_request
        try:
            if create:
                model_instance = self._endpoint_model.api_create(request)
            else:
                model_instance = self._retrieve_model_instance()
                model_instance = model_instance.api_update(request)
        except KeyError, e:
            logger.info(e)
            return self.bad_request

        if model_instance is None:
            return self.bad_request

        return self.get_json_response_for_instance(model_instance, request.user)

    def get_json_response_for_instance(self, model_instance, user):
        """
        A wrapper for getting a full json dictionary of a model instance.

        :param model_instance: The instance to dictify.
        :param user: The request user object
        :return: A json representation of the model instnace
        """
        model_instance_dict = model_instance.dictify_with_auth(user, short_dict=False)
        return self.valid_response(model_instance_dict)

    def _validate_request(self, request):
        """
        Validates an incoming request to ensure if follows a known URL pattern.
        Decides what type of request has come in, so that the calling method can
        dispatch to the correct handler.

        :param request: the request object
        :return: Boolean indicating the validity of the request
        """
        self._url_validator = APIUrl(request)

        if not self._url_validator.is_valid_request():
            return False

        if self._url_validator.is_reserved_url():
            return True

        self._endpoint_model = self.registered_endpoints.get(self._url_validator.REQUESTED_MODEL, None)

        if self._endpoint_model is None:
            return False

        return True

    @property
    def bad_request(self):
        """
        Shorthand for returning a 404 (BadJSONResponse)
        :return: BadJSONResponse object
        """
        return BadJSONResponse(status=StatusCode.NOT_FOUND)

    def valid_response(self, data):
        """
        Shorthand for returning a 200 JSON response with some data
        :param data: the data to be json-ified
        :return: UnsafeJSONResponse object
        """
        return UnsafeJSONResponse(data=data)

    def _handle_reserved_url_request(self, request):
        """
        Dispatches a (valid) reserved URL request to the correct handler
        :param request: the request object
        :return: Either the response of the handler, or a 404
        if the request wasn't valid
        """
        reserved_url = self._url_validator.RESERVED_URL

        if reserved_url == ReservedURL.LOGIN:
            return self.handle_login_request(request)
        elif reserved_url == ReservedURL.LOGOUT:
            return self.handle_logout_request(request)
        elif reserved_url == ReservedURL.CSRFTOKEN:
            return self.handle_csrf_request(request)

        return self.bad_request

    def handle_login_request(self, request):
        """
        Logs in a valid and active user.
        :param request: the request object with the user login credentials
        :return: A JSON representation of the return_on_login object,
        if the login was successful. If it wasn't, a 404 error is returned.
        """
        try:
            user = authenticate(username=request.POST['username'], password=request.POST['password'])
        except KeyError, e:
            logger.info(e)
            return self.bad_request

        if user is None or not user.is_active:
            return self.bad_request

        login(request, user)
        return self.get_json_response_for_instance(eval(self.return_on_login), user)

    def handle_logout_request(self, request):
        """
        Logs out the user (if logged in)
        :param request: the request object
        :return: 200 JSON response
        """
        logout(request)
        return self.valid_response(None)

    def handle_csrf_request(self, request):
        """
        Provides an empty 200 response which will always have a CSRF token header
        :param request: the request object
        :return: 200 JSON response
        """
        return self.valid_response(None)

    def handle_custom_request(self, request):
        """
        Dispatches a custom request to the endpoint model
        :param request: the request object
        :return: Either a good response if the endpoint model
        successfully handled the custom request, or a 404 if the
        request could not be handled
        """
        response = self._endpoint_model.api_custom_request(request)

        return self.valid_response(response) if response else self.bad_request