from bson import ObjectId
from mock import patch
from eduid_actions.testing import FunctionalTestCase


DUMMY_ACTION = {
        '_id': ObjectId('234567890123456789012301'),
        'user_oid': ObjectId('123467890123456789014567'),
        'action': 'dummy',
        'session': 'xyz',
        'preference': 100, 
        'params': {
            }
        }


class ActionTests(FunctionalTestCase):

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
