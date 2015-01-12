from abc import abstractmethod
from datetime import datetime

from django.db import models
from django.core.paginator import Paginator

__author__ = 'szpytfire'

class UserAuthCode(object):
    """
    Maintains verbose representations of the authorisation levels used
    in APIModel
    """
    PUBLIC = 1
    REGISTERED_USER = 2
    OWNER = 3

class ReservedPrefix(object):
    """
    Maintains the foreign model prefixes which are supported by APIModel
    """
    FK_SHORT = 'fk_short'
    FK_LONG = 'fk_long'
    REL_SHORT = 'rel_short'
    REL_LONG = 'rel_long'
    ONE_TO_ONE_SHORT = 'onetoone_short'
    ONE_TO_ONE_LONG = 'onetoone_long'
    MANY_TO_MANY_SHORT = 'm2m_short'
    MANY_TO_MANY_LONG = 'm2m_long'

class APIModel(models.Model):
    """
    Abstract Model which all API endpoints must inherit from.
    """

    # Deactivating a model is a common RESTful task
    # APIModel provides activte-related fields and handles deactivation
    # by default
    active = models.IntegerField(default=1)
    date_deactivated = models.DateTimeField(null=True)

    # Model fields which are publicly readable via the API
    public_fields = ()
    # Model fields which are only exposed to registered users
    registered_user_fields = ()
    # Model fields which are only exposed to owner(s) of the model instance
    # Ownership is determined by the implementation of is_owner()
    owner_only_fields = ()

    # Fields to be exposed when a short summary of the model instance is required
    short_description_fields = ()
    # Fields to be exposed when a full description of the model instance is required
    long_description_fields = ()

    # The default number of model instances to return in a get_all() request
    pagination = 10

    # The default readability of the model instance is set to a Public User
    _user_auth = UserAuthCode.PUBLIC

    # Prefixes which are used in field descriptions to indicate foreign model relationships
    _reserved_prefixes = [
        ReservedPrefix.FK_SHORT,
        ReservedPrefix.FK_LONG,
        ReservedPrefix.REL_SHORT,
        ReservedPrefix.REL_LONG,
        ReservedPrefix.ONE_TO_ONE_SHORT,
        ReservedPrefix.ONE_TO_ONE_LONG,
        ReservedPrefix.MANY_TO_MANY_SHORT,
        ReservedPrefix.MANY_TO_MANY_LONG
    ]

    def dictify(self, fields_to_include, ommit_related_fields):
        """
        Initiates the dictification process on the model instance using the fields passed in.
        Goes through each auth level up to the current user's auth level
        and calls dictify_helper with the fields corresponding to that level.

        Concatenates the result dictionaries together and returns.

        :param fields_to_include: Either the long or short description fields
        :param ommit_related_fields: Boolean denoting whether or not to dictify the related model fields.
        :return: A dictionary representation of the current instance.
        """
        dictified_fields = {}

        # always include public fields
        dictified_fields.update(self.dictify_helper(self.public_fields, fields_to_include, ommit_related_fields))

        # conditionally include registered user/owner fields
        if self._user_auth >= UserAuthCode.REGISTERED_USER:
            dictified_fields.update(self.dictify_helper(self.registered_user_fields, fields_to_include, ommit_related_fields))

            if self._user_auth == UserAuthCode.OWNER:
                dictified_fields.update(self.dictify_helper(self.owner_only_fields, fields_to_include, ommit_related_fields))

        return dictified_fields

    def dictify_helper(self, auth_level_fields, fields_to_include, ommit_related_fields):
        """
        Performs the actual dictification.
        Decides whether or not, based on the authentication level, whether the field should be
        added to the object dictionary.
        If the attribute begins with a reserved prefix (indicating a related model),
        it will dictify the foreign model and add it to the dictionary.

        :param auth_level_fields: Object fields to include for a given authentication level
        :param fields_to_include: Either short description or long description fields
        :param ommit_related_fields: Boolean to denote wehther or not to dictify related models
        :return:
        """

        # dictionary representation of the object
        dictified_fields = {}

        # go through each field and add it to the dictionary
        # if it's in list of fields for the authentication level
        for field in fields_to_include:
            if field in auth_level_fields:
                # extract the reserved prefix
                prefix = filter(lambda prefix: field.startswith(prefix), self._reserved_prefixes)

                # if the field doesn't begin with a reserved prefix
                # get the regular attribute/property
                if not prefix:
                    dictified_fields[field] = getattr(self, field, None)

                # do something special with the related model field
                # if we're allowed to dictify related models
                elif prefix and not ommit_related_fields:
                    # separate the prefix and actual related field name
                    prefix = prefix[0]
                    relation = field[len(prefix) + 1:]

                    # try and get the related model
                    val = getattr(self, relation, None)

                    # ommit the field if we can't find the related model
                    if val is None:
                      dictified_fields[relation] = None

                    # Perform a different dictification depending on what reserved prefix is used
                    # foreign models denoted by the related SHORT prefixes will be dictified short
                    # and similarly, related LONG will force a full dictification
                    # REL fields denote a one to many relationship. Thus, the corresponding models will be
                    # dictified into a list
                    elif prefix in [ReservedPrefix.FK_SHORT, ReservedPrefix.ONE_TO_ONE_SHORT]:
                        dictified_fields[relation] = val.dictify_with_auth(self._curr_user, ommit_related_fields=True)
                    elif prefix in [ReservedPrefix.FK_LONG, ReservedPrefix.ONE_TO_ONE_LONG]:
                        dictified_fields[relation] = val.dictify_with_auth(self._curr_user, short_dict=False, ommit_related_fields=True)
                    elif prefix in [ReservedPrefix.REL_SHORT, ReservedPrefix.MANY_TO_MANY_SHORT]:
                        dictified_fields[relation] = [rel.dictify_with_auth(self._curr_user, ommit_related_fields=True) for rel in val.all()]
                    elif prefix in [ReservedPrefix.REL_LONG, ReservedPrefix.MANY_TO_MANY_LONG]:
                        dictified_fields[relation] = [rel.dictify_with_auth(self._curr_user, short_dict=False, ommit_related_fields=True) for rel in val.all()]

        return dictified_fields

    def dictify_short(self, ommit_related_fields):
        """
        Dictifies only short description fields.

        :param ommit_related_fields: Boolean to determine whether to dictify related models
        :return: A short dictionary description of the model instance
        """
        return self.dictify(self.short_description_fields, ommit_related_fields)

    def dictify_long(self, ommit_related_fields):
        """
        Dictifies both short and long description fields.

        :param ommit_related_fields: Boolean to determine whether to dictify related models
        :return: A full dictionary description of the model instance
        """
        return self.dictify(self.short_description_fields + self.long_description_fields, ommit_related_fields)

    def dictify_with_auth(self, user, short_dict=True, ommit_related_fields=False):
        """
        Sets the authentication level on the model instance
        before dictifying.

        :param user: The request user
        :param short_dict: By default, only creates a short dictification.
        :param ommit_related_fields: By default allows dictifying of related models.
        :return: A dictionary representation of the model instance
        """

        # If the instance has been deactivated, the API will treat the resource as if it doesn't exist
        if not self.active:
            return None

        self.set_user_auth(user)

        return self.dictify_short(ommit_related_fields) if short_dict else self.dictify_long(ommit_related_fields)

    @classmethod
    def get_all(cls, page_number, user):
        """
        Dictifies endpoint model instances for the given page number.
        Returns up to the number of instances specified by the pagination variable.
        Dictifies the instances with dictify_with_auth which takes into consideration
        the user being passed in.

        :param page_number: The page number given to the paginator
        :param user: The request user
        :return: A list of short dictified model instances
        """
        objects = cls.objects.filter(active=1)
        p = Paginator(objects, cls.pagination)
        return [object.dictify_with_auth(user) for object in p.page(page_number).object_list]

    @classmethod
    def get_model_instance(cls, rest_param):
        """
        Provides a default implementation for getting an endpoint instance by its ID.

        :param rest_param: The endpoint instance criteria which has been passed in via the format:
        /<endpoint>/<endpoint_instance>/
        :return: The endpoint instance, or raises an ObjectDoesNotExist exception
        """
        return cls.objects.get(id=rest_param)

    @abstractmethod
    def is_owner(self, request_user):
        """
        This method has been left intentionally abstract to allow custom ownership of models.
        For example, a particular model may be owned by multiple users, or by a specific group of users.

        :param request_user: reference to request.user
        :return: True if the user has owner rights on the model
        """
        raise NotImplementedError

    def set_user_auth(self, user):
        """
        The default permission level set on all models is Public.
        This method takes in a user object and raises the permission
        level accordingly.

        :param user: The request user object
        :return: None
        """
        self._curr_user = user
        if user.is_authenticated():
            self._user_auth = UserAuthCode.REGISTERED_USER

            if self.is_owner(user):
                self._user_auth = UserAuthCode.OWNER

    @classmethod
    def api_create(cls, request):
        """
        Allows a model instance to be created via the API.

        By default the model is set to read only (the method returns None,
        which at an APIView level is exposed as a 404 error).

        Any model wishing to allow creation should override this method,
        making use of the request parameter.

        :param request: The request object
        :return: The newly created object (or None if one wasn't created).
        """
        return None

    def api_update(self, request):
        """
        Allows a model instance to be updated via the API.

        By default, it handles the process of deactivating a model instance,
        by looking out for the 'deactivate' parameter in the request.

        It also handles the save of any updates and returning the updated model.

        If this method is overwritten by a subclass, the subclass should call
        super api_update() at the END of the overwriting method to make use of this logic.

        Alternatively, subclasses can fully overwrite the method as they please.

        :param request: The request object
        :return: Updated instance of the model instance
        """
        if self.is_owner(request.user) and request.POST.get('deactivate'):
            self.active = 0
            self.date_deactivated = datetime.now()

        self.save()

        return self if self.active else None

    @classmethod
    def api_custom_request(cls, request):
        """
        Any "custom request" sent to the API for an endpoint will be
        forwarded to this method. Any model overriding this method
        will have access to the whole request so that it determine how to
        serve the custom request.

        The method defaults to returning False, which at an API level
        translates to the endpoint not supporting custom requests by default.

        :param request: The request object
        :return: Default to False, which propagates up as a 404 error.s
        """
        return False

    class Meta:
        abstract = True