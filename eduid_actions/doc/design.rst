
Proposal for a mechanism to interrupt the login process with arbitrary actions
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

The arbitrary actions will be stored in a new eduid_actions database.
When there are pending actions for a user that has issued a request to the
IdP, the IdP will give control to a new application, here called actions app,
that will let the users perform the required actions.

Database
========

There is a MongoDB db (let's call it eduid_actions for now) with a collection
for the actions that need to be performed, with schema:

Principal (ObjectId, required)
   identifies the user that must perform an action

Action (String, required)
   identifies the action to be performed

Session (String, optional)
   An identifier of the client session requiring the action,
   for the cases when the same principal opens sessions with different
   user agents simultaneously.

Preference (Int, required)
   A way to deterministically order the actions when a principal has
   more than one pending action.

Params (Dict, possibly empty)
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
   These actions would be specific for the particular request as well as for
   the principal, so the IdP would create a session identifier and add it
   to the document inserted in the eduid_actions db.

3. If any action is needed for the user, the process of issuing a SAML
   assertion is interrupted, and we redirect the user to the url of the
   actions app, with a URL like::

     https://actions.eduid.se/login?user=badal-kajil%040eduid.se&nonce=x&auth_token=y&session=z

4. The nonce and auth_token is an authentication mechanism based on a shared
   secret between the IdP and the actions app, to prove to the action app
   (without using SAML assertions) that the user has been authenticated by
   the IdP.

5. If we have inserted actions in the db with a session identifier (by
   examination of the SAML request), this identifier is sent to the
   actions app as a query param in the url.

The needed action is performed - or not
---------------------------------------

6. The actions app, once it validates the auth token sent by the IdP,
   retrieves from the eduid_actions db any actions that the user
   needs to perform, filters them with the session identifier if present,
   and orders them by preference.

7. The actions app, for each of the required actions,
   presents the user with some form, for example, the new terms of use and
   accept/reject buttons. The structure of this app will be explained in
   detail below, starting on point (9).

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
    actions, it proceeds to issue the assertion requested.

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
    a setuptools entry point. The name of the entry point will match the name of
    the action in the eduid_actions db, and the callable will return an object
    with a number of methods. The pyramid app will have a plugins registry, set
    up during initialization using ``pkg_resources.iter_entry_points``.

16. Once the app has decided which action needs to be performed next, and has
    selected the plugin objetc that corresponds to the action, it has to
    send a form to the user. Since some actions may need more than one step,
    the first method called on the object will be ``get_number_of_steps()``.
    
17. Then, for each needed step, the app will call
    ``get_action_body_for_step(step_number, request)``, that  will return a
    rendered jinja2 template, with the form that represents the step in the
    action that the user has to perform. This html will be
    inserted by the app into the body of a base template, and presented to the
    user.

18. After all steps for a given action have been performed, the actions app
    will call ``perform_action(request)`` on the plugin object, that
    will perform the required action (e.g., add an entry to the
    eduid_consent db).

19. Once the actions app has successfully consumed all required actions,
    it will return the user to the IdP. If any of them fails, it will inform
    the user that she cannot complete the request. The object provided by the
    plugin might have a method to return a message to inform the user why the
    process cannot be completed.

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
