__author__ = 'eperez'

import unittest
from cookielib import Cookie
from webtest import TestApp, TestRequest
from mock import patch
import pymongo
from pyramid.testing import DummyRequest, DummyResource
from pyramid.interfaces import ISessionFactory

from eduid_am.testing import MongoTemporaryInstance
from eduid_actions import main
from eduid_actions import views
from eduid_actions.action_abc import ActionPlugin


class DummyActionPlugin(ActionPlugin):

    translations = {}

    @classmethod
    def get_translations(cls):
        return cls.translations

    def get_number_of_steps(self):
        return 1

    def get_action_body_for_step(self, step_number, action, request):
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


class FunctionalTestCase(unittest.TestCase):
    """TestCase with an embedded MongoDB temporary instance.

    Each test runs on a temporary instance of MongoDB. The instance will
    be listen in a random port between 40000 and 5000.

    A test can access the connection using the attribute `conn`.
    A test can access the port using the attribute `port`
    """

    def setUp(self):
        super(FunctionalTestCase, self).setUp()
        self.tmp_db = MongoTemporaryInstance.get_instance()
        self.conn = self.tmp_db.conn
        self.port = self.tmp_db.port

        for db_name in self.conn.database_names():
            self.conn.drop_database(db_name)

        mongo_uri = 'mongodb://localhost:{0}/eduid_actions_test'
        mongo_uri = mongo_uri.format(str(self.port))

        settings = {
            'mongo_replicaset': None,
            'mongo_uri': mongo_uri,
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
            'session.lock_dir':'/tmp',
            'session.secret': '123456',
            'idp_url': 'http://example.com/idp',
        }

        if getattr(self, 'settings', None) is None:
            self.settings = settings
        else:
            self.settings.update(settings)
        try:
            app = main({}, **self.settings)
            self.testapp = TestApp(app)
            self.db = app.registry.settings['mongodb'].get_database()
        except pymongo.errors.ConnectionFailure:
            raise unittest.SkipTest("requires accessible MongoDB server")
        self.db.actions.drop()
        app.registry.settings['action_plugins']['dummy'] = DummyActionPlugin
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
