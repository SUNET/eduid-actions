__author__ = 'eperez'

import unittest
from webtest import TestApp, TestRequest
import pymongo
from pyramid.testing import DummyRequest

from eduid_am.testing import MongoTemporaryInstance
from eduid_actions import main
from eduid_actions.action_abc import ActionPlugin


class DummyActionPlugin(ActionPlugin):

    def get_number_of_steps(self):
        return 1

    def get_action_body_for_step(self, step_number, request):
        return u'Dummy action'

    def perform_action(self, request):
        if request.session.get('success', False):
            return
        else:
            raise self.ActionError(u'Dummy failure')


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
            'session.cookie_expires': '3600',
            'testing': True,
            'jinja2.directories': 'eduid_actions:templates',
            'jinja2.undefined': 'strict',
            'jinja2.i18n.domain': 'eduid_actions',
            'jinja2.filters': """ 
                route_url = pyramid_jinja2.filters:route_url_filter
                static_url = pyramid_jinja2.filters:static_url_filter
                """,
            'cache.type': 'memory',
            'cache.second.expire': 1,
            'cache.short_term.expire': 1,
            'cache.default_term.expire': 1,
            'cache.long_term.expire': 1,
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

    def tearDown(self):
        super(FunctionalTestCase, self).tearDown()
        for db_name in self.conn.database_names():
            self.conn.drop_database(db_name)
        self.testapp.reset()

    def add_to_session(self, data):
        queryUtility = self.testapp.app.registry.queryUtility
        session_factory = queryUtility(ISessionFactory)
        request = DummyRequest()
        session = session_factory(request)
        for key, value in data.items():
            session[key] = value
        session.persist()
        self.testapp.cookies['beaker.session.id'] = session._sess.id
