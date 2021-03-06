

eduID Actions application
+++++++++++++++++++++++++

The point of this application is to be able to interrupt the process
of issuing a SAML assertion by the 
`eduID IdP <https://github.com/SUNET/eduid-IdP>`_ and force the end user
to perform arbitrary actions before the IdP finally returns the response
to the SAML request. Examples of actions might be to sign a new version
of the terms o use, or force the user to change password.
The actions will be represented by documents in an actions collection
in an eduid_actions MongoDB database.
When there are pending actions for a user that has issued a request to the
IdP, the IdP will redirect the user to the actions app,
that will let the users perform the required actions, and, upon success,
redirect the user back to the IdP.

All the logic for each kind of action is provided by a plugin package,
that can declare a number of setuptools entry points that will be
described below.

Database
========

There is an ``eduid_actions`` MongoDB db with an ``actions`` collection
for the actions that need to be performed, with schema:

Principal (``user_oid``: ObjectId, required)
   identifies the user that must perform an action

Action (``action``: String, required)
   identifies the action to be performed

Session (``session``: String, optional)
   An identifier of the client session requiring the action,
   for the cases when the same principal opens sessions with different
   user agents simultaneously.

Preference (``preference``: Int, required)
   A way to deterministically order the actions when a principal has
   more than one pending action.

Params (``params``: Dict, possibly empty)
   An arbitrary dictionary of parameters specific for the action to be
   performed.

Example document::
  
   {'_id': ObjectId('234567890123456789012301'),
    'user_oid': ObjectId('123467890123456789014567'),
    'action': 'accept_tou',
    'session': 'xyz',
    'preference': 100
    'params': {
        'version': '2014-v2'
        }
    }

General Process
===============

On the IdP, before the action
-----------------------------

1. As soon as a user is identified, the IdP checks whether the user needs to 
   perform any action, querying the eduid_actions db.

2. Examination of the SAML request can result in adding actions to the db.
   These actions may be specific for the particular request as well as for
   the principal, so the IdP may create a session identifier and add it
   to the document inserted in the eduid_actions db.

3. If any action is needed for the user, the process of issuing a SAML
   assertion is interrupted, and we redirect the user to the
   actions app, with a URL like::

     https://actions.eduid.se/?userid=123467890123456789014567&token=abc&nonce=sdf&ts=1401093117

4. The nonce and auth_token is an authentication mechanism based on a shared
   secret between the IdP and the actions app, to prove to the action app
   (without using SAML assertions) that the user has been authenticated by
   the IdP.

5. If we have inserted actions in the db with a session identifier (by
   examination of the SAML request), this identifier is sent to the
   actions app as a query param in the url::

     https://actions.eduid.se/?userid=123467890123456789014567&token=abc&nonce=sdf&ts=1401093117&session=xyz

The needed action is performed - or not
---------------------------------------

6. The actions app, once it validates the auth token sent by the IdP,
   retrieves from the eduid_actions db any actions that the user
   needs to perform, filters them with the session identifier if present,
   and orders them by preference.

7. The actions app, for each of the required actions,
   presents the user with some form, for example, the new terms of use and
   accept/reject buttons. The structure of this app will be explained in
   detail below, starting on point (14).

8. The action may end in success, or not. It
   is responsibility of this app to act upon the user's action. If, for
   example, the user accepts the new terms of service, this app should record
   in the eduid_consent db the new acceptance of terms, and delete the entry
   in the eduid_actions db.
   
9. In the case where the action is not successfully performed,
   the workflow should end here.

10. We may need to set a record somewhere that some actions have already been
    performed for this user (appart from deleting the entry in the eduid_actions
    db), for the cases when these actions have arisen from
    examination of the SAML request, so that we do not enter a loop when we get
    back to the IdP.

11. Once all actions are successfully performed, the actions app will redirect
    the user back to the IdP.

On the IdP, after the action
----------------------------

12. Once the IdP re-authenticates the user, and sees that there are no pending
    actions, it proceeds to issue the assertion requested. Care must be taken
    for the case where there are actions pending for the user but for a different
    session.

13. Checking that there are no more actions to be performed may require
    more than querying the eduid_actions db, if some action stems from the
    particular SAML request being processed. In some cases it may be necessary
    to query some other db (e.g., the eduid_attributes_consent db).

The actions App
===============

14. This pyramid app should have 2 responsibilities: first, checking that the
    user has been authenticated by the IdP, by examining the token and nonce
    sent by the IdP; and second, letting the users perform the required actions.

15. Each action will be defined in a plugin, a package that is accessed through
    setuptools entry points. These plugins can define 4 different entry points:
    one for adding new actions, another for acting upon a pending action, and
    2 others for updating the central user db with any new data that may have
    been collected when performing the action.

16. For adding new actions, the plugin must be installed in the python
    environment where the IdP runs. It must declare an entry point named
    ``eduid_actions.add_actions``, pointing to a callable that accepts as
    arguments an instance of an IdP application
    (``eduid_idp.idp:IdPApplication``), a user object
    (``eduid_userdb.user:User``), and an IdP ticket
    (``eduid_idp.login.SSOLoginData``).

17. For acting upon a pending action, the plugin must be installed in the
    python environment where the actions app runs. It must declare an
    entry point named ``eduid_actions.action``, pointing to a python class
    with a number of methods. The API
    of the objects returned by the plugins is described in the
    ``eduid_actions.action_abc:ActionPlugin`` abstract base class.

18. Once the app has decided which action needs to be performed next, and has
    selected the plugin object that corresponds to the action, it has to
    send a form to the user. Since some actions may need more than one step,
    the first method called on the object will be ``get_number_of_steps()``.

19. Then, for each needed step, the app will call
    ``get_action_body_for_step(step_number, request)``, that  will return a
    rendered jinja2 template, with the form that represents the step in the
    action that the user has to perform. This html will be
    inserted by the app into the body of a base template, and presented to the
    user.

20. After all steps for a given action have been performed, the actions app
    will call ``perform_action(request)`` on the plugin object, that
    will perform the required action (e.g., add an entry to the
    eduid_consent db).

21. Once the actions app has successfully consumed all required actions,
    it will return the user to the IdP. If any of them fails, it will inform
    the user that she cannot complete the request: the object provided by the
    plugin will raise an ``ActionError`` exception that will carry a
    localized message that will be shown to the user.

22. If an action has recorded some information that needs to end up in the
    central user db, the plugin may act as an AM plugin. For this, it must
    be installed in the python environment where the AM app runs, and it
    must declare 2 entry points. The first, named ``eduid_am.plugin_init``,
    must point to a callable that accepts a dictionary with am configuration
    data, and returns an object that has attributes needed by the attribute
    fetcher. The second, named ``eduid_am.attribute_fetcher``, must point to
    a callable that accepts as arguments the object provided by the first
    entry point and an user id (``bson.ObjectId``), and returns a dictionary
    ready to use by pymongo to update the user object with the provided id
    in the central user db.
    More details about AM plugins in the eduid-am package.

Examples of actions
===================

a. ToU - The user has to accept a new version of the terms of use.

b. 2FA - user is trying to log in to some resource demanding additional
   information. The IdP only did password authentication, and wants the
   action_app to do some additional authentication (could be hardware token or
   SMS code for example). Maybe there would be a separate plugin per
   authentication type .

c. CAPTCHA - not sure one wants to captcha after verifying the password was
   right, but perhaps... we should just keep the possibility in mind when
   designing this.

d. Announcements for downtime, new features or whatever.

e. Attribute release consent (per SP or even per login). This one might add a
   requirement to be able to communicate richer results to the IdP than just True
   or False. If the result is to be stored per SP the result of the action plugin
   would probably be stored in MongoDB somewhere, but maybe there will be a need
   to add URI parameters with return value to the URL used to return the user to
   the IdP? This plugin will be important.

f. Password change - we will require users to change password every X years.

Configuration
=============

The configuration parameters that are specific for this application are:

auth_shared_secret
    A string to be shared with the IdP, used to authenticate the request.

mongo_uri
    The URI of the MongoDB that holds the actions collection

idp_url
    The URL of the IdP, where the app will redirect the user once there are no
    more pending actions
