import os
import re

import logging

from pkg_resources import resource_filename
from pkg_resources import iter_entry_points

from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.i18n import get_locale_name
from pyramid_beaker import session_factory_from_settings
from pyramid.interfaces import IStaticURLInfo
from pyramid.config.views import StaticURLInfo

from pyramid.httpexceptions import HTTPNotFound
from pyramid.httpexceptions import HTTPForbidden, HTTPBadRequest
from pyramid.httpexceptions import HTTPMethodNotAllowed
from pyramid.httpexceptions import HTTPInternalServerError

from eduid_am.db import MongoDB
from eduid_am.celery import celery
from eduid_am.config import read_setting_from_env, read_mapping
from eduid_actions.i18n import locale_negotiator
from eduid_actions.context import RootFactory


log = logging.getLogger('eduid_actions')


class PluginsRegistry(dict):

    def __init__(self, name, settings):
        for entry_point in iter_entry_points(name):
            if entry_point.name in self:
                log.warn("Duplicate entry point: %s" % entry_point.name)
            else:
                log.debug("Registering entry point: %s" % entry_point.name)
                self[entry_point.name] = entry_point.load()
                package_name = 'eduid_action.' + entry_point.name
                locale_path = resource_filename(package_name, 'locale')
                self[entry_point.name].init_languages(settings, locale_path,
                                                      entry_point.name)


class ConfiguredHostStaticURLInfo(StaticURLInfo):

    def generate(self, path, request, **kw):
        host = request.registry.settings.get('static_assets_host_override', None)
        kw.update({'_host': host})
        return super(ConfiguredHostStaticURLInfo, self).generate(path,
                                                                 request,
                                                                 **kw)


def jinja2_settings(settings):
    settings.setdefault('jinja2.i18n.domain', 'eduid-actions')
    settings.setdefault('jinja2.newstyle', True)

    settings.setdefault('jinja2.extensions', ['jinja2.ext.with_'])

    settings.setdefault('jinja2.directories', 'eduid_actions:templates')
    settings.setdefault('jinja2.undefined', 'strict')
    settings.setdefault('jinja2.filters', """
        route_url = pyramid_jinja2.filters:route_url_filter
        static_url = pyramid_jinja2.filters:static_url_filter
    """)


def includeme(config):
    # DB setup
    settings = config.registry.settings
    mongo_replicaset = settings.get('mongo_replicaset', None)
    if mongo_replicaset is not None:
        mongodb = MongoDB(db_uri=settings['mongo_uri'],
                          replicaSet=mongo_replicaset)
    else:
        mongodb = MongoDB(db_uri=settings['mongo_uri'])

    config.registry.settings['mongodb'] = mongodb
    config.registry.settings['db_conn'] = mongodb.get_connection

    config.set_request_property(lambda x: x.registry.settings['mongodb'].get_database(), 'db', reify=True)

    # configure Celery broker
    broker_url = read_setting_from_env(settings, 'broker_url', 'amqp://')
    celery.conf.update(BROKER_URL=broker_url)
    settings['celery'] = celery
    settings['broker_url'] = broker_url

    # Favicon
    config.add_route('favicon', '/favicon.ico')
    # Errors
    config.add_route('error404', '/error404/')
    config.add_view(context=HTTPNotFound,
                    view='eduid_actions.views.not_found_view',
                    renderer='error404.jinja2')
    config.add_route('forbidden403', '/error403/')
    config.add_view(context=HTTPForbidden,
                    view='eduid_actions.views.forbidden_view',
                    renderer='error403.jinja2')
    config.add_route('badrequest400', '/error400/')
    config.add_view(context=HTTPBadRequest,
                    view='eduid_actions.views.bad_request_view',
                    renderer='error400.jinja2')
    config.add_route('notallowed405', '/error405/')
    config.add_view(context=HTTPMethodNotAllowed,
                    view='eduid_actions.views.method_not_allowed_view',
                    renderer='error405.jinja2')
    config.add_route('error500', '/error500/')
    config.add_view(context=HTTPInternalServerError,
                    view='eduid_actions.views.exception_view',
                    renderer='error500.jinja2')
    config.add_view(context=Exception,
                    view='eduid_actions.views.exception_view',
                    renderer='error500.jinja2')

    config.add_route('actions', '/')
    config.add_route('perform-action', '/perform-action')

    # Plugin registry
    settings['action_plugins'] = PluginsRegistry('eduid_actions.action',
                                                 settings)


def main(global_config, **settings):
    """ This function returns a WSGI application.

    It is usually called by the PasteDeploy framework during
    ``paster serve``.
    """
    settings = dict(settings)

    # Parse settings before creating the configurator object
    available_languages = read_mapping(settings, 'available_languages',
                                       default={'en': 'English',
                                                'sv': 'Svenska'})

    settings['lang_cookie_domain'] = read_setting_from_env(settings,
                                                           'lang_cookie_domain',
                                                           None)

    settings['lang_cookie_name'] = read_setting_from_env(settings,
                                                         'lang_cookie_name',
                                                         'lang')

    for item in (
        'mongo_uri',
        'site.name',
        'auth_shared_secret',
    ):
        settings[item] = read_setting_from_env(settings, item, None)
        if settings[item] is None:
            raise ConfigurationError(
                'The {0} configuration option is required'.format(item))

    mongo_replicaset = read_setting_from_env(settings, 'mongo_replicaset',
                                             None)
    if mongo_replicaset is not None:
        settings['mongo_replicaset'] = mongo_replicaset

    try:
        settings['session.expire'] = int(settings.get('session.expire', 3600))
    except ValueError:
        raise ConfigurationError('session.expire should be a valid integer')

    try:
        settings['session.timeout'] = int(settings.get(
            'session.timeout',
            settings['session.expire'])
        )
    except ValueError:
        raise ConfigurationError('session.expire should be a valid integer')

    settings['available_languages'] = available_languages

    jinja2_settings(settings)

    session_factory = session_factory_from_settings(settings)
    config = Configurator(settings=settings,
                          root_factory=RootFactory,
                          locale_negotiator=locale_negotiator)

    config.registry.registerUtility(ConfiguredHostStaticURLInfo(),
                                    IStaticURLInfo)

    config.set_session_factory(session_factory)

    config.set_request_property(get_locale_name, 'locale', reify=True)

    locale_path = read_setting_from_env(settings, 'locale_dirs',
                                        'eduid_actions:locale')
    config.add_translation_dirs(locale_path)

    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('set_language', '/set_language/')

    # eudid specific configuration
    includeme(config)
    for plugin in config.registry.settings['action_plugins'].values():
        plugin.includeme(config)

    config.scan(ignore=[re.compile('.*tests.*').search, '.testing'])

    return config.make_wsgi_app()
