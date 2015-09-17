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

import time
import atexit
import random
import shutil
import tempfile
import unittest
import subprocess
import os
import pymongo

from webtest import TestApp
from mock import patch

from eduid_actions import main
from eduid_actions import views
from eduid_actions.action_abc import ActionPlugin


class DummyActionPlugin(ActionPlugin):

    translations = {}

    @classmethod
    def get_translations(cls):
        return cls.translations

    def get_number_of_steps(self):
        return self._steps

    def get_action_body_for_step(self, step_number, action, request, errors=None):
        if action['params'].get('body_failure', False):
            raise self.ActionError(u'Body failure')
        else:
            return u'''
                       <h1>Dummy action</h1>
                       <form id="dummy" method="POST" action="#">
                           <input type="submit" name="submit" value="submit">
                           <input type="submit" name="reject" value="reject">
                       </form>'''

    def perform_action(self, action, request):
        if action['params'].get('perform_failure', False):
            raise self.ActionError(u'Perform failure')
        elif request.POST.get('reject', False):
            raise self.ActionError(u'Action not performed')
        else:
            return


class DummyActionPlugin1(DummyActionPlugin):

    _steps = 1


class DummyActionPlugin2(DummyActionPlugin):

    _steps = 2


class MongoTemporaryInstance(object):
    """Singleton to manage a temporary MongoDB instance

    Use this for testing purpose only. The instance is automatically destroyed
    at the end of the program.

    """
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
            atexit.register(cls._instance.shutdown)
        return cls._instance

    def __init__(self):
        self._tmpdir = tempfile.mkdtemp()
        self._port = random.randint(40000, 50000)
        self._process = subprocess.Popen(['mongod', '--bind_ip', 'localhost',
                                          '--port', str(self._port),
                                          '--dbpath', self._tmpdir,
                                          '--nojournal', '--nohttpinterface',
                                          '--noauth', '--smallfiles',
                                          '--syncdelay', '0',
                                          '--nssize', '1', ],
                                         stdout=open(os.devnull, 'wb'),
                                         stderr=subprocess.STDOUT)

        # XXX: wait for the instance to be ready
        #      Mongo is ready in a glance, we just wait to be able to open a
        #      Connection.
        for i in range(10):
            time.sleep(0.2)
            try:
                self._conn = pymongo.Connection('localhost', self._port)
            except pymongo.errors.ConnectionFailure:
                continue
            else:
                break
        else:
            self.shutdown()
            assert False, 'Cannot connect to the mongodb test instance'

    @property
    def conn(self):
        return self._conn

    @property
    def port(self):
        return self._port

    def shutdown(self):
        if self._process:
            self._process.terminate()
            self._process.wait()
            self._process = None
            shutil.rmtree(self._tmpdir, ignore_errors=True)


class FunctionalTestCase(unittest.TestCase):
    """TestCase with an embedded MongoDB temporary instance.

    Each test runs on a temporary instance of MongoDB. The instance will
    be listen in a random port between 40000 and 5000.

    A test can access the connection using the attribute `conn`.
    A test can access the port using the attribute `port`
    """

    def setUp(self):
        super(FunctionalTestCase, self).setUp()
        try:
            self.tmp_db = MongoTemporaryInstance.get_instance()
        except OSError:
            raise unittest.SkipTest("requires accessible mongod executable")
        self.conn = self.tmp_db.conn
        self.port = self.tmp_db.port

        for db_name in self.conn.database_names():
            self.conn.drop_database(db_name)

        settings = {
            'mongo_replicaset': None,
            'mongo_uri': 'mongodb://localhost:{0}/eduid_actions_test',
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
            'idp_url': 'http://example.com/idp',
        }

        if getattr(self, 'settings', None) is None:
            self.settings = settings
        else:
            self.settings.update(settings)
        for key in self.settings:
            if key.startswith('mongo_uri'):
                self.settings[key] = self.settings[key].format(str(self.port))
        app = main({}, **self.settings)
        self.testapp = TestApp(app)
        self.db = app.registry.settings['mongodb'].get_database()
        app = self.testapp.app
        self.db.actions.drop()
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
        self.db.actions.drop()
        for db_name in self.conn.database_names():
            self.conn.drop_database(db_name)
        self.testapp.reset()
        self.patcher.stop()
