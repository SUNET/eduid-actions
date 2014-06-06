import os
import re

import logging

from pkg_resources import resource_filename
from pkg_resources import iter_entry_points

from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.i18n import get_locale_name
from pyramid_beaker import session_factory_from_settings

from eduid_am.db import MongoDB
from eduid_am.config import read_setting_from_env, read_mapping, read_list
from eduid_actions.i18n import locale_negotiator


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
                self[entry_point.name].init_languages(settings, locale_path)


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

    # Favicon
    config.add_route('favicon', '/favicon.ico')

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
                          locale_negotiator=locale_negotiator)
    config.set_session_factory(session_factory)

    config.set_request_property(get_locale_name, 'locale', reify=True)

    locale_path = read_setting_from_env(settings, 'locale_dirs',
                                        'eduid_actions:locale')
    config.add_translation_dirs(locale_path)

    config.add_static_view('static', 'static', cache_max_age=3600)
    config.add_route('set_language', '/set_language/')

    # eudid specific configuration
    includeme(config)
    config.scan(ignore=[re.compile('.*tests.*').search, '.testing'])

    return config.make_wsgi_app()
