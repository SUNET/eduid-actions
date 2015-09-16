from copy import deepcopy
from bson import ObjectId
from mock import patch
from eduid_actions.testing import FunctionalTestCase


DUMMY_ACTION = {
        '_id': ObjectId('234567890123456789012301'),
        'user_oid': ObjectId('123467890123456789014567'),
        'action': 'dummy',
        'preference': 100, 
        'params': {
            }
        }


class ActionTests(FunctionalTestCase):

    def test_set_language(self):
        self.db.actions.insert(DUMMY_ACTION)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/set_language/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117&lang=sv')
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')

    def test_action_success(self):
        self.db.actions.insert(DUMMY_ACTION)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get(res.location)
        form = res.forms['dummy']
        self.assertEqual(self.db.actions.find({}).count(), 1)
        res = form.submit('submit')
        self.assertEqual(self.db.actions.find({}).count(), 0)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/perform-action')
        res = self.testapp.get(res.location)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, self.settings['idp_url'])

    def test_action_2steps_success(self):
        action = deepcopy(DUMMY_ACTION)
        action['_id'] = ObjectId('234567890123456789012302')
        action['action'] = 'dummy_2steps'
        self.db.actions.insert(action)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get(res.location)
        form = res.forms['dummy']
        self.assertEqual(self.db.actions.find({}).count(), 1)
        res = form.submit('submit')
        form = res.forms['dummy']
        self.assertEqual(self.db.actions.find({}).count(), 1)
        res = form.submit('submit')
        self.assertEqual(self.db.actions.find({}).count(), 0)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/perform-action')
        res = self.testapp.get(res.location)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, self.settings['idp_url'])

    def test_two_actions_success(self):
        self.db.actions.insert(DUMMY_ACTION)
        action2 = deepcopy(DUMMY_ACTION)
        action2['_id'] = ObjectId('234567890123456789012302')
        action2['action'] = 'dummy2'
        action2['preference'] = 200
        self.db.actions.insert(action2)
        self.assertEqual(self.db.actions.find({}).count(), 2)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get(res.location)
        form = res.forms['dummy']
        res = form.submit('submit')
        self.assertEqual(self.db.actions.find({}).count(), 1)
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get(res.location)
        form = res.forms['dummy']
        res = form.submit('submit')
        self.assertEqual(self.db.actions.find({}).count(), 0)

    def test_method_not_allowed(self):
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        res = self.testapp.put(url, expect_errors=True)
        self.assertEqual(res.status, '404 Not Found')
        res = self.testapp.get(url, expect_errors=True)
        res = self.testapp.put(res.location, expect_errors=True)
        self.assertEqual(res.status, '405 Method Not Allowed')

    def test_forbidden(self):
        url = ('/perform-action')
        res = self.testapp.get(url, expect_errors=True)
        self.assertEqual(res.status, '403 Forbidden')

    def test_action_failure(self):
        fail_action = deepcopy(DUMMY_ACTION)
        fail_action['params']['body_failure'] = True
        self.db.actions.insert(fail_action)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get(res.location)
        self.assertIn('Body failure', res.body)
        self.assertNotIn('submit', res.body)
        self.assertEqual(self.db.actions.find({}).count(), 1)

    def test_perform_failure(self):
        fail_action = deepcopy(DUMMY_ACTION)
        fail_action['params']['perform_failure'] = True
        self.db.actions.insert(fail_action)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get(res.location)
        form = res.forms['dummy']
        self.assertEqual(self.db.actions.find({}).count(), 1)
        res = form.submit('submit')
        self.assertIn('Perform failure', res.body)
        self.assertEqual(self.db.actions.find({}).count(), 1)

    def test_perform_not_performed(self):
        self.db.actions.insert(DUMMY_ACTION)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get(res.location)
        form = res.forms['dummy']
        self.assertEqual(self.db.actions.find({}).count(), 1)
        res = form.submit('reject')
        self.assertIn('Action not performed', res.body)
        self.assertEqual(self.db.actions.find({}).count(), 1)

    def test_insufficient_params(self):
        self.db.actions.insert(DUMMY_ACTION)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf')
        res = self.testapp.get(url, expect_errors=True)
        self.assertEqual(res.status, '400 Bad Request')
        self.assertIn('Insufficient authentication params', res.body)
        self.assertEqual(self.db.actions.find({}).count(), 1)

    def test_fail_token_auth(self):
        self.db.actions.insert(DUMMY_ACTION)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=fail_verify'
                '&token=abc&nonce=sdf&ts=1401093117')
        res = self.testapp.get(url, expect_errors=True)
        self.assertEqual(res.status, '400 Bad Request')
        self.assertIn('Token authentication has failed', res.body)
        self.assertEqual(self.db.actions.find({}).count(), 1)

    def test_no_actions(self):
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        self.assertEqual(self.db.actions.find({}).count(), 0)
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/perform-action')
        res = self.testapp.get(res.location)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, self.settings['idp_url'])
        self.assertEqual(self.db.actions.find({}).count(), 0)

    def test_action_success_with_session(self):
        fail_action = deepcopy(DUMMY_ACTION)
        fail_action['session'] = 'abcd'
        self.db.actions.insert(fail_action)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567&session=abcd&'
                '&token=abc&nonce=sdf&ts=1401093117')
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get(res.location)
        form = res.forms['dummy']
        self.assertEqual(self.db.actions.find({}).count(), 1)
        res = form.submit('submit')
        self.assertEqual(self.db.actions.find({}).count(), 0)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/perform-action')
        res = self.testapp.get(res.location)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, self.settings['idp_url'])

    def test_action_with_different_session(self):
        fail_action = deepcopy(DUMMY_ACTION)
        fail_action['session'] = 'abcd'
        self.db.actions.insert(fail_action)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567&session=xyzw&'
                '&token=abc&nonce=sdf&ts=1401093117')
        self.assertEqual(self.db.actions.find({}).count(), 1)
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/perform-action')
        res = self.testapp.get(res.location)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, self.settings['idp_url'])
        self.assertEqual(self.db.actions.find({}).count(), 1)

    def test_action_with_no_session_in_url(self):
        fail_action = deepcopy(DUMMY_ACTION)
        fail_action['session'] = 'abcd'
        self.db.actions.insert(fail_action)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567&'
                '&token=abc&nonce=sdf&ts=1401093117')
        self.assertEqual(self.db.actions.find({}).count(), 1)
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/perform-action')
        res = self.testapp.get(res.location)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, self.settings['idp_url'])
        self.assertEqual(self.db.actions.find({}).count(), 1)

    def test_two_actions_one_with_session(self):
        self.db.actions.insert(DUMMY_ACTION)
        action2 = deepcopy(DUMMY_ACTION)
        action2['_id'] = ObjectId('234567890123456789012302')
        action2['action'] = 'dummy2'
        action2['session'] = 'abcd'
        action2['preference'] = 200
        self.db.actions.insert(action2)
        self.assertEqual(self.db.actions.find({}).count(), 2)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get(res.location)
        form = res.forms['dummy']
        res = form.submit('submit')
        self.assertEqual(self.db.actions.find({}).count(), 1)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/perform-action')
        res = self.testapp.get(res.location)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, self.settings['idp_url'])
        self.assertEqual(self.db.actions.find({}).count(), 1)

    def test_two_actions_with_different_session(self):
        self.db.actions.insert(DUMMY_ACTION)
        action2 = deepcopy(DUMMY_ACTION)
        action2['_id'] = ObjectId('234567890123456789012302')
        action2['action'] = 'dummy2'
        action2['session'] = 'abcd'
        action2['preference'] = 200
        self.db.actions.insert(action2)
        self.assertEqual(self.db.actions.find({}).count(), 2)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567&session=xyzf'
                '&token=abc&nonce=sdf&ts=1401093117')
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get(res.location)
        form = res.forms['dummy']
        res = form.submit('submit')
        self.assertEqual(self.db.actions.find({}).count(), 1)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, 'http://localhost/perform-action')
        res = self.testapp.get(res.location)
        self.assertEqual(res.status, '302 Found')
        self.assertEqual(res.location, self.settings['idp_url'])
        self.assertEqual(self.db.actions.find({}).count(), 1)

    def test_two_actions_with_same_session(self):
        self.db.actions.insert(DUMMY_ACTION)
        action2 = deepcopy(DUMMY_ACTION)
        action2['_id'] = ObjectId('234567890123456789012302')
        action2['action'] = 'dummy2'
        action2['session'] = 'abcd'
        action2['preference'] = 200
        self.db.actions.insert(action2)
        self.assertEqual(self.db.actions.find({}).count(), 2)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567&session=abcd'
                '&token=abc&nonce=sdf&ts=1401093117')
        res = self.testapp.get(url)
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get(res.location)
        form = res.forms['dummy']
        res = form.submit('submit')
        self.assertEqual(self.db.actions.find({}).count(), 1)
        self.assertEqual(res.status, '302 Found')
        res = self.testapp.get(res.location)
        form = res.forms['dummy']
        res = form.submit('submit')
        self.assertEqual(self.db.actions.find({}).count(), 0)
