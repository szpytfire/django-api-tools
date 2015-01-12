from django_api_tools.APIModel import APIModel

from django.db import models
from django.core.validators import MaxLengthValidator
from django.contrib.auth.models import User

__author__ = 'szpytfire'

class TestProfile(APIModel):
    user = models.OneToOneField(User, unique=True, related_name='test_profile')

    def is_owner(self, request_user):
        return request_user.test_profile == self

    @classmethod
    def api_create(cls, request):
        return None

class Foo(APIModel):
    owner = models.ForeignKey(TestProfile, related_name='foos')
    f1 = models.IntegerField(default=1)
    f2 = models.TextField(validators=[MaxLengthValidator(10)])

    public_fields = ('id',)
    registered_user_fields = ('f1', 'onetoone_short_owner')
    owner_only_fields = ('f2',)


    short_description_fields = public_fields
    long_description_fields = public_fields + registered_user_fields + owner_only_fields

    def is_owner(self, request_user):
        return request_user.test_profile == self.owner

    @classmethod
    def api_create(cls, request):
        foo = Foo.objects.create(owner=request.user.test_profile, f2=request.POST['f2'])
        return foo

    def api_update(self, request):
        if not self.is_owner(request.user):
            return None

        if request.POST.get('f1'):
            self.f1 += 1

        return super(Foo, self).api_update(request)

class BarBaz(APIModel):
    f1 = models.IntegerField(default=1)
    public_fields = ('id',)
    registered_user_fields = ()

    short_description_fields = public_fields
    long_description_fields = public_fields + registered_user_fields

    def is_owner(self, request_user):
        return True

    @classmethod
    def api_create(cls, request):
        bar = Bar.objects.create()
        return bar

    def api_update(self, request):
        if not self.is_owner(request.user):
            return None

        if request.POST.get('f1'):
            self.f1 += 1

        return super(BarBaz, self).api_update(request)

    class Meta:
        abstract = True

class Bar(BarBaz):
    baz = models.ForeignKey('Baz', related_name='bars')
    registered_user_fields = ('f1', 'fk_short_baz')

class Baz(BarBaz):
    registered_user_fields = ('f1', 'rel_short_bars')

class Qux(BarBaz):
    owner = models.ForeignKey(Baz, related_name='quxs')
    foos = models.ManyToManyField(Foo)

    @classmethod
    def api_custom_request(cls, request):
        return "yo!"