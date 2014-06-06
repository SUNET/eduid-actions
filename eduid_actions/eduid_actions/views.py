import os.path
from bson import ObjectId

from pyramid.view import view_config
from pyramid.response import FileResponse
from pyramid.httpexceptions import HTTPFound, HTTPNotFound, HTTPBadRequest
from pyramid.settings import asbool
from pyramid.renderers import render_to_response

from eduid_actions.auth import verify_auth_token

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

#def verify_auth_token(*args):
#    return True

@view_config(route_name='actions', renderer='main.jinja2')
def actions(request):
    '''
    '''
    userid = request.GET.get('userid')
    token = request.GET.get('token')
    nonce = request.GET.get('nonce')
    timestamp = request.GET.get('ts')
    shared_key = request.registry.settings.get('auth_shared_secret')

    if verify_auth_token(shared_key, userid, token, nonce, timestamp):
        request.session['userid'] = userid
        return HTTPFound(location='/perform-action')
    else:
        logger.info("Token authentication failed (userid: {!r})".format(userid))
        # Show and error, the user can't be logged
        return HTTPBadRequest()


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
            return HTTPBadRequest()
        if self.request.method == 'GET':
            return self.get()
        return self.post()

    def get(self):
        self.get_next_action()
        session = self.request.session
        plugin_obj = session['current_plugin']
        action = session['current_action']
        try:
            html = plugin_obj.get_action_body_for_step(1, action,
                                                       self.request)
        except plugin_obj.ActionError as exc:
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
                html = u'<h2>{0}</h2>'.format(exc.args[0])
                return render_to_response('action-form.jinja2',
                                          {'plugin_html': html},
                                          request=self.request)
            self.request.db.actions.find_and_modify(
                    {'_id': action['_id']},
                    remove=True)
            return HTTPFound(location='/perform-action')
        next_step = session['current_step'] + 1
        session['current_step'] = next_step
        try:
            html = plugin_obj.get_action_body_for_step(next_step,
                                                       action,
                                                       self.request)
        except plugin_obj.ActionError as exc:
            html = u'<h2>{0}</h2>'.format(exc.args[0])
        return render_to_response('main.jinja2',
                                  {'plugin_html': html},
                                  request=self.request)

    def get_next_action(self):
        session = self.request.session
        settings = self.request.registry.settings
        userid = session['userid']
        actions = self.request.db.actions.find({'user_oid': ObjectId(userid)})
        if not actions:
            return HTTPFound(location=settings['idp_url'])
        action = sorted(actions, key=lambda x: x['preference'])[-1]
        name = action['action']
        if name not in settings['action_plugins']:
            logger.info("Missing plugin for action {0}".format(name))
            raise HTTPBadRequest()
        session['current_action'] = action
        session['current_step'] = 1
        plugin_obj = settings['action_plugins'][name]()
        session['current_plugin'] = plugin_obj
        session['total_steps'] = plugin_obj.get_number_of_steps()
