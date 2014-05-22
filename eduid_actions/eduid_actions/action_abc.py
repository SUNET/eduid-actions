
from abc import ABCMeta, abstractmethod


class ActionPlugin:
    __metaclass__ = ABCMeta

    class ActionError(Exception):
        '''
        exception to be raised if the action to be performed fails,
        either in `get_action_body_for_step`, or in `perform_action`.
        Instantiated with a message that informs about the reason for
        the failure.

        Example code (obj is an action object, an instance of a class
        that extends ActionPlugin, defined in a plugin)::

          try:
              obj.perform_action(request)
          except obj.ActionError as exc:
              failure_msg = exc.args[0]

        :param arg: the reason for the failure
        :type arg: unicode
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
    def get_action_body_for_step(self, step_number, request):
        '''
        Return the html form that corresponds to step number
        `step_number`. If there is some error in the process,
        raise ActionError.

        :param step_number: the step number
        :param request: the request
        :returns: the html to be presented to the user for the next step
        :raise: ActionPlugin.ActionError

        :type step_number: int
        :type request: pyramid.request.Request
        :rtype: unicode


        '''

    @abstractmethod
    def perform_action(self, request):
        '''
        Once the user has completed all steps required to
        perform this action, we should have all neccesary
        information in the request that the user sent back
        in response to the last form.
        So, here we try to perform the action.
        If we succeed we return None, and raise ActionError otherwise.

        :param request: the request
        :type request: pyramid.request.Request
        :raise: ActionPlugin.ActionError
        '''
