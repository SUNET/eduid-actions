#
# Copyright (c) 2015 NORDUnet A/S
# All rights reserved.
#
#   Redistribution and use in source and binary forms, with or
#   without modification, are permitted provided that the following
#   conditions are met:
#
#     1. Redistributions of source code must retain the above copyright
#        notice, this list of conditions and the following disclaimer.
#     2. Redistributions in binary form must reproduce the above
#        copyright notice, this list of conditions and the following
#        disclaimer in the documentation and/or other materials provided
#        with the distribution.
#     3. Neither the name of the NORDUnet nor the names of its
#        contributors may be used to endorse or promote products derived
#        from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
from abc import ABCMeta, abstractmethod
import gettext


class ActionError(Exception):
    '''
    exception to be raised if the action to be performed fails,
    either in `get_action_body_for_step`, or in `perform_action`.
    Instantiated with a message that informs about the reason for
    the failure.
    The message should never carry any sensitive information, since
    it will besent to the user.
    
    The rm kwarg indicates to the actions app whether it should
    remove the action record from the db when encountering
    this exception.

    Example code, in the plugin::
    
      if test_some_condition(*args, **kwargs):
          follow_success_code_path(*args2, **kwargs2)
      else:
          msg = _('Failure condition')
          raise self.ActionError(msg)
    
    Example code, in the actions app (obj is an action object,
    an instance of a class that extends ActionPlugin,
    defined in a plugin, and actions_db is an instance of
    eduid_userdb.actions.db.ActionsDB)::

      try:
          obj.perform_action(request)
      except obj.ActionError as exc:
          if exc.remove_action:
              actions_db.remove_action_by_id(action.action_id)
          failure_msg = exc.args[0]
          # return a 200 Ok with the failure_msg

    :param arg: the reason for the failure
    :type arg: unicode
    '''

    def __init__(self, msg, rm=False):
        super(ActionError, self).__init__(msg)
        self.remove_action = rm


class ActionPlugin:
    '''
    Abstract class to be extended by the different plugins for the
    eduid_actions app.
    The derived classes in the plugins are set as the objects to which
    the entry point ``eduid_actions.action`` in those plugins point at.

    The packages for the plugins must have a name with the form
    ``eduid_action.<name>``, where <name> must coincide with the key in
    the entry point.
    For example, if we have a plugin ``eduid_action.tou``,
    that defines a class ``ToUPlugin`` (subclass of ``ActionPlugin``) in
    its ``__init__.py``, we would have as entry point in its ``setup.py``::

        
      entry_points="""
        [eduid_actions.action]
            tou = eduid_action.tou:ToUPlugin
      """,

    '''

    __metaclass__ = ABCMeta

    ActionError = ActionError

    @classmethod
    @abstractmethod
    def get_translations(cls):
        '''
        return a dictionary in which the keys are the codes for
        the available languages, and the values are the gettext
        translation instances. This dict may be a class attribute of
        subclasses of ``ActionPlugin``.

        The first time it is called, from within the ``init_languages``
        classmethod of this same class, it will return an empty dict,
        to be filled by that method.

        :returns: the gettext translations
        :rtype: dict
        '''

    @classmethod
    def init_languages(cls, settings, locale_path, plugin_name):
        '''
        initialize the translations dictionary returned by
        ``get_translations`` for the available languages in
        ``settings`` and the provided locale_path.

        :param settings: the settings object
        :param locale_path: the path to the locales directory

        :type settings: pyramid.config.settings.Settings
        :type locale_path: str
        '''
        translations = cls.get_translations()
        available_languages = settings['available_languages'].keys()
        domain = 'eduid_action.' + plugin_name
        for lang in available_languages:
            translations[lang] = gettext.translation(domain,
                                                     locale_path,
                                                     languages=[lang])

    def get_language(self, request):
        '''
        get the language code that corresponds to the given request.

        :param request: the request
        :returns: the language code

        :type request: pyramid.request.Request
        :rtype: str
        '''
        settings = request.registry.settings
        available_languages = settings['available_languages'].keys()
        cookie_name = settings['lang_cookie_name']

        cookie_lang = request.cookies.get(cookie_name, None)
        if cookie_lang and cookie_lang in available_languages:
            return cookie_lang

        locale_name = request.accept_language.best_match(available_languages)

        if locale_name not in available_languages:
            locale_name = settings.get('default_locale_name', 'sv')
        return locale_name

    def get_ugettext(self, request):
        '''
        get the ugettext method that corresponds to the given request.

        :param request: the request
        :returns: the ugettext method

        :type request: pyramid.request.Request
        :rtype: function
        '''
        lang = self.get_language(request)
        return self.get_translations()[lang].ugettext

    class ValidationError(Exception):
        '''
        exception to be raised if some form doesn't validate,
        either in `get_action_body_for_step`, or in `perform_action`.
        Instantiated with a dict of field names to error messages.

        :param arg: error messages for each field
        :type arg: dict
        '''

    @classmethod
    @abstractmethod
    def includeme(self, config):
        '''
        Plugin specific configuration for the eduid_actions app.

        :param config: the pyramid configurator for the wsgi app.
        :type arg: pyramid.config.Configurator
        '''

    @abstractmethod
    def get_number_of_steps(self):
        '''
        The number of steps that the user has to take
        in order to complete this action.
        In other words, the number of html forms
        that will be sequentially sent to the user.

        :returns: the number of steps
        :rtype: int
        '''

    @abstractmethod
    def get_action_body_for_step(self, step_number, action, request, errors=None):
        '''
        Return the html form that corresponds to step number
        `step_number`. If there is some error in the process,
        raise ActionError.

        :param step_number: the step number
        :param action: the action as retrieved from the eduid_actions db
        :param request: the request
        :param errors: validation errors
        :returns: the html to be presented to the user for the next step
        :raise: ActionPlugin.ActionError

        :type step_number: int
        :type action: dict
        :type request: pyramid.request.Request
        :type errors: dict
        :rtype: unicode


        '''

    @abstractmethod
    def perform_action(self, action, request):
        '''
        Once the user has completed all steps required to
        perform this action, we should have all neccesary
        information in the request that the user sent back
        in response to the last form.
        So, here we try to perform the action.
        If we succeed we return None, and raise ActionError otherwise.

        :param request: the request
        :param action: the action as retrieved from the eduid_actions db

        :type request: pyramid.request.Request
        :type action: dict
        :raise: ActionPlugin.ActionError
        '''
