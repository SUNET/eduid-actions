import os.path

from pyramid.view import view_config
from pyramid.response import FileResponse
from pyramid.httpexceptions import HTTPFound, HTTPNotFound, HTTPBadRequest
from pyramid.settings import asbool

from eduid_actions.auth import verify_auth_token

import logging
logger = logging.getLogger('eduid_actions')


@view_config(name='favicon.ico')
def favicon_view(context, request):
    path = os.path.dirname(__file__)
    icon = os.path.join(path, 'static', 'favicon.ico')
    return FileResponse(icon, request=request)


@view_config(route_name='home', renderer='main.jinja2')
def home(request):
    '''
    '''
    context = {'plugin_html': 'testing'}

    return context


@view_config(route_name='set_language', request_method='GET')
def set_language(context, request):
    settings = request.registry.settings
    lang = request.GET.get('lang', 'en')
    if lang not in settings['available_languages']:
        return HTTPNotFound()

    url = request.environ.get('HTTP_REFERER', None)
    if url is None:
        url = request.route_path('home')
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
        remember_headers = remember(request, userid)
        request.session['next-action'] = action

        return HTTPFound(location='/perform-action/', headers=remember_headers)
    else:
        logger.info("Token authentication failed (userid: {!r})".format(userid))
        # Show and error, the user can't be logged
        return HTTPBadRequest()


@view_config(route_name='perform-action')
class PerformAction(object):
    '''
    XXX work in progress
    '''
