import os.path
from bson import ObjectId

from pyramid.view import view_config
from pyramid.response import FileResponse
from pyramid.settings import asbool
from pyramid.renderers import render_to_response

from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.httpexceptions import HTTPForbidden, HTTPBadRequest
from pyramid.httpexceptions import HTTPMethodNotAllowed
from pyramid.httpexceptions import HTTPInternalServerError

from eduid_actions.auth import verify_auth_token
from eduid_actions.i18n import TranslationString as _

import logging
logger = logging.getLogger('eduid_actions')


@view_config(name='favicon.ico')
def favicon_view(context, request):
    path = os.path.dirname(__file__)
    icon = os.path.join(path, 'static', 'favicon.ico')
    return FileResponse(icon, request=request)


@view_config(route_name='set_language', request_method='GET')
def set_language(context, request):
    settings = request.registry.settings
    lang = request.GET.get('lang', 'en')
    if lang not in settings['available_languages']:
        return HTTPNotFound()

    url = request.environ.get('HTTP_REFERER', None)
    if url is None:
        url = request.route_path('actions')
    response = HTTPFound(location=url)

    cookie_domain = settings.get('lang_cookie_domain', None)
    cookie_name = settings.get('lang_cookie_name')

    extra_options = {}
    if cookie_domain is not None:
        extra_options['domain'] = cookie_domain

    extra_options['httponly'] = asbool(settings.get('session.httponly'))
    extra_options['secure'] = asbool(settings.get('session.secure'))

    response.set_cookie(cookie_name, value=lang, **extra_options)

    return response


@view_config(route_name='actions',
             renderer='main.jinja2',
             request_method='GET')
def actions(request):
    '''
    '''
    userid = request.GET.get('userid')
    token = request.GET.get('token')
    nonce = request.GET.get('nonce')
    timestamp = request.GET.get('ts')
    if not (userid and token and nonce and timestamp):
        msg = _('Insufficient authentication params')
        return HTTPBadRequest(msg)
    shared_key = request.registry.settings.get('auth_shared_secret')

    if verify_auth_token(shared_key, userid, token, nonce, timestamp):
        logger.info("Starting pre-login actions "
                    "for userid: {0})".format(userid))
        request.session['userid'] = userid
        request.session['idp_session'] = request.GET.get('session', None)
        return HTTPFound(location='/perform-action')
    else:
        logger.info("Token authentication failed (userid: {0})".format(userid))
        # Show and error, the user can't be logged
        msg = _('Token authentication has failed, '
                'you do not seem to come from a listed IdP')
        return HTTPBadRequest(msg)


@view_config(route_name='perform-action')
class PerformAction(object):
    '''
    '''

    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self):
        if self.request.session.get('userid', None) is None:
            logger.info("Unidentified user")
            return HTTPForbidden()
        if self.request.method == 'GET':
            return self.get()
        elif self.request.method == 'POST':
            return self.post()
        return HTTPMethodNotAllowed()

    def get(self):
        self.get_next_action()
        session = self.request.session
        plugin_obj = session['current_plugin']
        action = session['current_action']
        logger.info('Starting pre-login action {0} '
                    'for userid {1}'.format(action['action'],
                                            session['userid']))
        try:
            html = plugin_obj.get_action_body_for_step(1, action,
                                                       self.request)
        except plugin_obj.ActionError as exc:
            self._log_aborted(action, session, exc)
            html = u'<h2>{0}</h2>'.format(exc.args[0])
        return render_to_response('main.jinja2',
                                  {'plugin_html': html},
                                  request=self.request)

    def post(self):
        session = self.request.session
        plugin_obj = session['current_plugin']
        action = session['current_action']
        if session['total_steps'] == session['current_step']:
            try:
                plugin_obj.perform_action(action, self.request)
            except plugin_obj.ActionError as exc:
                self._log_aborted(action, session, exc)
                html = u'<h2>{0}</h2>'.format(exc.args[0])
                return render_to_response('main.jinja2',
                                          {'plugin_html': html},
                                          request=self.request)
            self.request.db.actions.find_and_modify(
                    {'_id': action['_id']},
                    remove=True)
            logger.info('Finished pre-login action {0} '
                        'for userid {1}'.format(action['action'],
                                                session['userid']))
            return HTTPFound(location='/perform-action')
        next_step = session['current_step'] + 1
        session['current_step'] = next_step
        try:
            html = plugin_obj.get_action_body_for_step(next_step,
                                                       action,
                                                       self.request)
        except plugin_obj.ActionError as exc:
            self._log_aborted(action, session, exc)
            html = u'<h2>{0}</h2>'.format(exc.args[0])
        return render_to_response('main.jinja2',
                                  {'plugin_html': html},
                                  request=self.request)

    def get_next_action(self):
        session = self.request.session
        settings = self.request.registry.settings
        userid = session['userid']
        actions = self.request.db.actions.find({'user_oid': ObjectId(userid)})
        if not actions.count():
            logger.info("Finished pre-login actions "
                        "for userid: {0}".format(userid))
            raise HTTPFound(location=settings['idp_url'])
        else:
            if session['idp_session'] is not None:
                actions = [a for a in actions if (not a.get('session', False) or
                                        a['session'] == session['idp_session'])]
                msg_no_actions = ("Finished pre-login actions "
                            "for userid: {0} and session: {1}".format(userid,
                                                        session['idp_session']))
            else:
                actions = [a for a in actions if not a.get('session', False)]
                msg_no_actions = ("Finished pre-login actions "
                                  "for userid: {0}".format(userid))
            if not actions:
                logger.info(msg_no_actions)
                raise HTTPFound(location=settings['idp_url'])
        action = sorted(actions, key=lambda x: x['preference'])[-1]
        if not ('user_oid' in action and 'action' in action and
                'preference' in action and 'params' in action):
            logger.info("Malformed action {0}".format(str(action['_id'])))
            raise HTTPInternalServerError()
        name = action['action']
        if name not in settings['action_plugins']:
            logger.info("Missing plugin for action {0}".format(name))
            raise HTTPInternalServerError()
        session['current_action'] = action
        session['current_step'] = 1
        plugin_obj = settings['action_plugins'][name]()
        session['current_plugin'] = plugin_obj
        session['total_steps'] = plugin_obj.get_number_of_steps()

    def _log_aborted(self, action, session, exc):
        logger.info('Aborted pre-login action {0} for userid {1}, '
                    'reason: {2}'.format(action['action'],
                                         session['userid'],
                                         exc.args[0]))


def exception_view(context, request):
    logger.error("The error was: %s" % context, exc_info=(context))
    request.response.status = 500 
    return {}


def not_found_view(context, request):
    request.response.status = 404 
    return {}


def forbidden_view(context, request):
    request.response.status = 403
    return {}


def bad_request_view(context, request):
    request.response.status = 400
    msg = context.args[0]
    return {'msg': msg}


def method_not_allowed_view(context, request):
    request.response.status = 405
    return {}
