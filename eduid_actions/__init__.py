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

import re

import logging

from pkg_resources import resource_filename
from pkg_resources import iter_entry_points

from pyramid.config import Configurator
from pyramid.exceptions import ConfigurationError
from pyramid.i18n import get_locale_name

from pyramid.httpexceptions import HTTPNotFound
from pyramid.httpexceptions import HTTPForbidden, HTTPBadRequest
from pyramid.httpexceptions import HTTPMethodNotAllowed
from pyramid.httpexceptions import HTTPInternalServerError

from eduid_userdb.actions import ActionDB
from eduid_userdb.userdb import UserDB
from eduid_am.celery import celery
from eduid_common.config.parsers import IniConfigParser
from eduid_actions.i18n import locale_negotiator
from eduid_actions.context import RootFactory
from eduid_actions.session import SessionFactory


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
    # Config parser
    cp = IniConfigParser('')  # Init without config file as it is already loaded

    # DB setup
    settings = config.registry.settings
    actions_db = ActionDB(settings['mongo_uri'])

    config.registry.settings['actions_db'] = actions_db

    config.set_request_property(lambda x: x.registry.settings['actions_db'],
                                'actions_db', reify=True)
    mongo_uri = cp.read_setting_from_env(settings, 'mongo_uri')
    amdb = UserDB(mongo_uri, 'eduid_am')   # XXX hard-coded name of old userdb. How will we transition?

    config.registry.settings['amdb'] = amdb

    config.set_request_property(lambda x: x.registry.settings['amdb'],
                                'amdb', reify=True)

    # configure Celery broker
    broker_url = cp.read_setting_from_env(settings, 'broker_url', 'amqp://')
    celery_conf = {
        'BROKER_URL': broker_url,
        'MONGO_URI': mongo_uri,
        'CELERY_TASK_SERIALIZER': 'json',
        'CELERY_RESULT_BACKEND': 'amqp',
    }
    celery.conf.update(celery_conf)
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

    cp = IniConfigParser('')  # Init without config file as it is already loaded

    # Parse settings before creating the configurator object
    available_languages = cp.read_mapping(settings, 'available_languages',
                                          default={'en': 'English',
                                                   'sv': 'Svenska'})

    settings['lang_cookie_domain'] = cp.read_setting_from_env(settings,
                                                              'lang_cookie_domain',
                                                              None)

    settings['lang_cookie_name'] = cp.read_setting_from_env(settings,
                                                            'lang_cookie_name',
                                                            'lang')

    for item in (
        'mongo_uri',
        'site.name',
        'auth_shared_secret',
    ):
        settings[item] = cp.read_setting_from_env(settings, item, None)
        if settings[item] is None:
            raise ConfigurationError(
                'The {0} configuration option is required'.format(item))

    mongo_replicaset = cp.read_setting_from_env(settings, 'mongo_replicaset',
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

    config = Configurator(settings=settings,
                          root_factory=RootFactory,
                          locale_negotiator=locale_negotiator)

    settings['REDIS_HOST'] = cp.read_setting_from_env(settings, 'redis_host',
                                                      'redis.docker')

    settings['REDIS_PORT'] = int(cp.read_setting_from_env(settings, 'redis_port',
                                                          6379))

    settings['REDIS_DB'] = int(cp.read_setting_from_env(settings, 'redis_db', 0))

    settings['REDIS_SENTINEL_HOSTS'] = cp.read_list(
        settings,
        'redis_sentinel_hosts',
        default=[])
    settings['REDIS_SENTINEL_SERVICE_NAME'] = cp.read_setting_from_env(settings, 'redis_sentinel_service_name',
                                                                       'redis-cluster')

    session_factory = SessionFactory(settings)
    config.set_session_factory(session_factory)

    config.set_request_property(get_locale_name, 'locale', reify=True)

    locale_path = cp.read_setting_from_env(settings, 'locale_dirs',
                                           'eduid_actions:locale')
    config.add_translation_dirs(locale_path)

    if settings.get('static_url', False):
        config.add_static_view(settings['static_url'], 'static')
    else:
        config.add_static_view('static', 'static', cache_max_age=3600)

    config.add_route('set_language', '/set_language/')

    # eudid specific configuration
    includeme(config)
    for plugin in config.registry.settings['action_plugins'].values():
        plugin.includeme(config)

    config.scan(ignore=[re.compile('.*tests.*').search, '.testing'])

    return config.make_wsgi_app()
