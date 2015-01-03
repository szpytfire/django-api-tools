# Django API add-on #

## Overview ##

*Django API add-on is a mini-framework which allows developers to run RESTful APIs alongside websites using Forms/Templates.*

* Simple integration with an existing project - choose a subset of models to be served by the API.
* RESTful JSON endpoints created for your chosen Django models - no need to hard code URLs.
* Endpoint routing to application specific logic. GET (Read), POST (Create, Update, Deactivate) operations supported by default.
* Allows the addition of custom endpoints. 
* Authentication via Django's user auth mechanism - provides a means for logging users in and out, as well as custom user permissions on model instances.


# APIView #

APIView is Django API add-on's custom class based view. RESTful endpoints are automatically created for each model registered with APIView. Note, that the models registered with APIView must be a sub-class of APIModel. This allows APIView to take care of routing and responding to requests. For a full set of URLs that are created for each registered model, see "RESTful URLs" below.

The add-on offers developers the flexibility in choosing database models to be exposed by the API, and at a lower level, individual model attributes that can be exposed, see "Defining Ownership" below.

*** Example views.py using APIView: ***

```
python

from api_tools.APIView import APIView
from example.models import Foo, Bar, Profile


class ExampleAPIView(APIView):
    # models can map to custom endpoint names
    registered_endpoints = {
        'f': Foo,
        'bar': Bar,
        'profile': Profile
    }

    # Optional attribute:
    # models which allow instances to be created without authentication
    public_create_endpoints = (Profile, )
    
    # Optional attribute:
    # models which allow instances to be updated without authentication
    public_update_endpoints = (Bar, )

    # The statement evaluated upon a successful user login
    # This should be a subclass of APIModel which can be dictified and returned as JSON
    return_on_login = 'user.profile'
```

*** Hook up your API View to your urls.py: ***

```
python
from django.conf.urls import patterns, include, url
from django.views.decorators.csrf import ensure_csrf_cookie
from example.views import PollsAPIView

# An arbitrary URL prefix, which if matched, forwards requests to the APIView
API_PREFIX = 'api'

urlpatterns = patterns('',
    .
    .
    .
    url(r'^{}/'.format(API_PREFIX), ensure_csrf_cookie(ExampleAPIView.as_view())),
)
```

### Logging in ###
``` POST /api/login/ ``` requires the parameters **username** and **password**. If the login is unsuccessful; either as a result of incorrect credentials or an inactive user, the API will return an empty 404 response. A successful login will both set an authenticated session and *dictify* the eval()'d **return_on_login** variable.

**return_on_login**: It is often the case that upon a successful login, a user's profile page is displayed to the user. By having to define return_on_login in APIView, the add-on allows flexibility over what APIModel is dictified and returned to the authenticated user.

### Logging out ###
``` POST /api/logout/ ``` will delete the user's authenticated session (if logged in), and return an empty 200 response.

### Public Endpoints ###
Applications often require users to sign up. By default, the add-on requires users either creating or updating a model instance to be authenticated. With this behaviour, APIView would reject any sign up (create) requests. Any models registered in **public_create_endpoints** and **public_update_endpoints** are excepted from the default behaviour. Note however, 

### RESTful URLs ###

Each model registered in APIView is automatically provided the following URLs:

**Get a list of resource instances:**

```GET /api/<endpoint>/?page=n ```

*Where n is an optional integer parameter defaulting to 1.*

Each page of results will return, by default, up to 10 resource instances. Where less than 10 instances are returned for a given page, it is safe to assume that there are no more pages.

*Returns:*

* An array of **short** dictionary objects.   
* An empty 404 response for an invalid page number or a request to a non-existent page.

**Get an individual resource:**

``` GET /api/<endpoint>/<instance>/ ```

*Where instance is a unique identifier handled by the specific endpoint. By default, the identifier is treated as a Django model internal id.*

*Returns:*

* A **long** dictionary representation of the model instance. 
* An empty 404 response if a model instance can't be found, and a custom request mapping can't be found.

*Notes:*

If no instance is found, APIView will treat the request as a custom request on the endpoint model. It will route the request to the model's ```api_custom_request(cls, request) ``` classmethod. You are free to implement custom request however you wish.

**Custom request**

```GET /api/<endpoint>/<instance>/<custom_field>/<custom_field2>/.../.../```

*Where there can be an arbitrary number of custom fields.*

*Returns:*

* An empty 404 response by default, unless code handling the custom request has been implemented.

**Create a new resource:**

```POST /api/<endpoint>/```

*Notes:*

The create request is routed to the endpoint's implementation of ``api_create(cls, request)``.

*Returns:*

* A **long** dictionary representation of the created model instance.
* An empty 404 response if an instance could not be created.

**Update an existing resource:**

```POST /api/<endpoint>/<instance>/```

*Notes:*

The update request is routed to the endpoint's implementation of ``api_update(cls, request)``.

*Returns:*

* A **long** dictionary representation of the updated model instance.
* An empty 404 response if updating failed.


# APIModel #
APIModel is Django API add-on's custom abstract model class. Each model registered with APIView must be a subclass of APIModel and implement the abstract methods *is_owner*, *api_create* and *api_update*.


APIModel handles the *dictification* of instances, that is, creating a dictionary representation of the model instance. See "Dictification" for a more detailed article.

## Defining Ownership ##
Django API allows model attributes to be divided into three authentication levels:

* Those that can be exposed to the public
* Those that only registered users of the application can view
* Those that can only be viewed by the owner(s) of a particular model instance.

Django API add-on uses Django's standard user authentication system. Thus, much of the authentication revolves around extracting the **request_user** (request.user) and testing its authentication level against a model instance.

Django API add-on assumes that the underlying application can deduce, from the request user, the ownership status that user has over a particular model instance.

**We highly recommend that your application has a model (inheriting from APIModel) with a 1:1 mapping to User.**

In the examples below we call this model *Profile*:
```
python
class Profile(APIModel):
    user = models.OneToOneField(User, unique=True, related_name='profile')
```

Having this kind of setup provides a mechanism for extending Django's user model; we can add application-specific fields to Profile, such as *eye_colour*, which can then be extracted from a request via the notation ```request.user.profile.eye_colour```. Furthermore, having this setup provides a basis for authenticating "owners" against model instances.

Sub-classes of APIModel must implement the abstract method ```is_owner(self, request_user)```.

### Example 1: No ownership ###

Suppose we he had an application with a "Wall" which could be read from, written to, and modified by the public.
In this scenario, for any user, APIModel would always return True for any user.

```
python
class Wall(APIModel):
    .
    .
    .
    def is_owner(self, request_user):
        return True
```

### Example 2: Individual user ownership ###

Suppose our application was changed, such that each "Wall" now had an individual owner.
We could change ```is_owner``` to return True if the requesting user was the owner of the Wall.

```
python
class Profile(APIModel):
    user = models.OneToOneField(User, unique=True, related_name='profile')


class Wall(APIModel):
    owner = models.ForeignKey(Profile, related_name='walls')
    .
    .
    .
    def is_owner(self, request_user):
        return request_user.profile == self.owner
```

### Example 3: Group ownership ###

We could change our application further so that each "Wall" is owned by a "Group", and that Groups consist of Profiles.
```is_owner``` would now return True if the requesting user was a member of the Group which owned the Wall.

```
python
class Group(APIModel):
    .
    .
    .

class Profile(APIModel):
    user = models.OneToOneField(User, unique=True, related_name='profile')
    group = models.ForeignKey(Group, related_name='members')

class Wall(APIModel):
    owner = models.ForeignKey(Profile, related_name='walls')
    group = models.ForeignKey(Group, related_name='walls')
    .
    .
    .
    def is_owner(self, request_user):
        return request_user.profile.group == self.group
```

## Dictification ##

Dictification is the process of creating a dictionary representation of a model instance. 
Although this process is largely taken care of by the underlying APIModel class, subclasses of APIModel must specify what attributes should be used.

### Long & Short Dictionaries ###

There are two types of dictification:

* Short - A partial dictionary representation of an object. Only dictifies attributes listed in the *short_description_fields*.
* Long - A full dictionary representation of an object. Dictifies attributes listed in both *short_description_fields* and *long_description_fields*.

**Example 1:**

```
python
class Choice(APIModel):
    text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)
    
    short_description_fields = (id, )
    long_description_fields = (text, votes, )

```

```
c = Choice.obects.create(text='foo')

c.dictify_short()
>> {"id":1}

c.dictify_long()
>> {"id": 1, "text": "foo", "votes": 0}
```

### Foreign Model attributes ###

Naturally, models are often related to other models.
API add-on supports both short and long dictification of related models:

*  Related - prefix "rel_short" or "rel_long"
*  One-to-One - prefix "onetoone_short" or "onetoone_long"
*  Foreign Key - prefix "fk_short" or "fk_long"
*  Many-to-Many - prefix "m2m_short" or "m2m_long"

**Example 2:**

```
python
class Choice(APIModel):
    text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)
    
    short_description_fields = (id, )
    long_description_fields = (text, votes, rel_long_bars)

class Foo(APIModel):
    choice = models.ForeignKey(Choice, related_name='bars')
    text = models.CharField(max_length=200)

    short_description_fields = (id, )
    long_description_fields = (text, fk_long_text)
```

Upon dictification, APIModel would recognise the attribute *rel_long_bars* as a related key named bars, and create a long dictification of the related model. If instead the attribute was named *rel_short_bars*, the related model would only be dictified as a short dictio


### Authentication ###

An APIModel's fields can be divided into three categories:

* public_fields - Those that 
* registered_user_fields
* owner_only_fields


# Quickstart Guide #

Working with the Django quickstart guide:
```
https://docs.djangoproject.com/en/dev/intro/tutorial01/
```

We change **views.py** to use the Class-based API view:
```
python

from api_tools.APIView import APIView
from polls.models import Question, Choice, Profile


class PollsAPIView(APIView):
    # models can map to custom endpoint names
    registered_endpoints = {
        'question': Question,
        'choice': Choice,
        'profile': Profile
    }

    # models which allow instances to be created by the public
    public_create_endpoints = (Profile, )

    # the endpoint instance whose JSON dictionary should be returned upon a successful user login
    return_on_login = 'user.profile'
```

**urls.py** must be changed to use the class-based view:

```
python
from django.conf.urls import patterns, include, url
from django.views.decorators.csrf import ensure_csrf_cookie
from polls.views import PollsAPIView

urlpatterns = patterns('',
    url(r'^api/', ensure_csrf_cookie(PollsAPIView.as_view())),
)
```

Note here that your API URLs don't necessarily have to start with /api/.

Finally, we must update **models.py**

```
python
from datetime import datetime

from api_tools.APIModel import APIModel

from django.db import models
from django.contrib.auth.models import User

class Profile(APIModel):
    user = models.OneToOneField(User, unique=True, related_name='profile')
    .
    .
    .

class Question(APIModel):
    question_text = models.CharField(max_length=200)
    pub_date = models.DateTimeField('date published')

    public_fields = ('id', 'question_text', 'pub_date')

    def is_owner(self, request_user):
        # No ownership in this basic model setup, so everyone is treated as an owner
        return True

    @classmethod
    def api_create(cls, request):
        q = Question.objects.create(question_text=request.POST['question'], pub_date=datetime.now())
        return q

class Choice(APIModel):
    question = models.ForeignKey(Question)
    choice_text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)
```