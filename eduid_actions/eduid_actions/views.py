import os.path

from pyramid.view import view_config
from pyramid.response import FileResponse
from pyramid.httpexceptions import HTTPFound, HTTPNotFound
from pyramid.settings import asbool


@view_config(name='favicon.ico')
def favicon_view(context, request):
    path = os.path.dirname(__file__)
    icon = os.path.join(path, 'static', 'favicon.ico')
    return FileResponse(icon, request=request)


@view_config(route_name='home', renderer='templates/main.jinja2')
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
