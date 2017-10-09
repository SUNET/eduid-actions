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

__author__ = 'eperez'

import copy

from mock import patch
from webtest import TestApp

from eduid_actions import main
from eduid_actions import views
from eduid_actions.action_abc import ActionPlugin

from eduid_am.celery import celery, get_attribute_manager
from eduid_userdb.testing import MongoTestCase
from eduid_common.api.testing import RedisTemporaryInstance

from logging import getLogger
logger = getLogger(__name__)

_SETTINGS = {
    'mongo_replicaset': None,
    'site.name': 'Test Site',
    'auth_shared_secret': '123123',
    'testing': True,
    'pyramid.includes': '''
                pyramid_jinja2
                pyramid_beaker
                ''',
    'jinja2.directories': 'eduid_actions:templates',
    'jinja2.undefined': 'strict',
    'jinja2.i18n.domain': 'eduid-actions',
    'jinja2.filters': """
                route_url = pyramid_jinja2.filters:route_url_filter
                static_url = pyramid_jinja2.filters:static_url_filter
                """,
    'session.type': 'memory',
    'session.key': 'session',
    'session.lock_dir': '/tmp',
    'session.secret': '123456',
    'session.cookie_max_age': 3600,
    'idp_url': 'http://example.com/idp',
    }


class DummyActionPlugin(ActionPlugin):

    translations = {}

    @classmethod
    def get_translations(cls):
        return cls.translations

    def get_number_of_steps(self):
        return self._steps

    def get_action_body_for_step(self, step_number, action, request, errors=None):
        if action.params.get('body_failure', False):
            raise self.ActionError(u'Body failure')
        else:
            return None, u'''
                       <h1>Dummy action</h1>
                       <form id="dummy" method="POST" action="#">
                           <input type="submit" name="submit" value="submit">
                           <input type="submit" name="reject" value="reject">
                       </form>'''

    def perform_action(self, action, request):
        if action.params.get('perform_failure', False):
            raise self.ActionError(u'Perform failure')
        elif request.POST.get('reject', False):
            raise self.ActionError(u'Action not performed', rm=True)
        else:
            return


class DummyActionPlugin1(DummyActionPlugin):

    _steps = 1


class DummyActionPlugin2(DummyActionPlugin):

    _steps = 2


class FunctionalTestCase(MongoTestCase):
    """TestCase with an embedded MongoDB temporary instance.

    Each test runs on a temporary instance of MongoDB. The instance will
    be listen in a random port between 40000 and 5000.

    A test can access the connection using the attribute `conn`.
    A test can access the port using the attribute `port`
    """

    def setUp(self):

        settings = copy.deepcopy(_SETTINGS)

        if getattr(self, 'settings', None) is None:
            self.settings = settings
        else:
            self.settings.update(settings)

        super(FunctionalTestCase, self).setUp(celery, get_attribute_manager)

        settings['mongo_uri'] = self.tmp_db.get_uri('eduid_actions_test')
        self.redis_instance = RedisTemporaryInstance.get_instance()
        self.settings['redis_host'] = 'localhost'
        self.settings['redis_port'] = self.redis_instance._port
        self.settings['redis_db'] = '0'

        app = main({}, **self.settings)

        self.actions_db = app.registry.settings['actions_db']
        self.actions_db._drop_whole_collection()

        self.testapp = TestApp(app)
        app = self.testapp.app
        app.registry.settings['action_plugins']['dummy'] = DummyActionPlugin1
        app.registry.settings['action_plugins']['dummy2'] = DummyActionPlugin1
        app.registry.settings['action_plugins']['dummy_2steps'] = DummyActionPlugin2

        def mock_verify_auth_token(*args, **kwargs):
            if args[1] == 'fail_verify':
                return False
            return True

        mock_config = {'new_callable': lambda: mock_verify_auth_token}
        self.patcher = patch.object(views, 'verify_auth_token', **mock_config)
        self.patcher.start()

    def tearDown(self):
        super(FunctionalTestCase, self).tearDown()
        self.actions_db._drop_whole_collection()
        for db_name in self.conn.database_names():
            self.conn.drop_database(db_name)
        self.testapp.reset()
        self.patcher.stop()
