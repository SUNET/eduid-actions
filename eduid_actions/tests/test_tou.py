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

from copy import deepcopy
from bson import ObjectId
from eduid_actions.testing import FunctionalTestCase


DUMMY_ACTION = {
        '_id': ObjectId('234567890123456789012301'),
        'user_oid': ObjectId('123467890123456789014567'),
        'action': 'tou',
        'preference': 100, 
        'params': {
            'version': 'test-version'
            }
        }


class ToUActionTests(FunctionalTestCase):

    def setUp(self, *args, **kwargs):
        try:
            import eduid_action.tou
        except ImportError:
            self.skipTest('The ToU plugin is necessary for these tests')
        super(ToUActionTests, self).setUp(*args, **kwargs)

    def test_tou(self):
        self.actions_db.add_action(data=DUMMY_ACTION)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        res1 = self.testapp.get(url)
        self.assertEqual(res1.status, '302 Found')
        res2 = self.testapp.get(res1.location)
        form = res2.forms['tou-form']
        self.assertEqual(self.actions_db.db_count(), 1)
        res3 = form.submit('accept')
        self.assertEqual(self.actions_db.db_count(), 0)
        res4 = self.testapp.get(res3.location)
        self.assertIn(self.settings['idp_url'], res4.location)

    def test_tou_not_accepted(self):
        self.actions_db.add_action(data=DUMMY_ACTION)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        res1 = self.testapp.get(url)
        self.assertEquals(res1.status, '302 Found')
        res2 = self.testapp.get(res1.location)
        form = res2.forms['tou-form']
        self.assertEquals(self.actions_db.db_count(), 1)
        res3 = form.submit('reject')
        self.assertEquals(self.actions_db.db_count(), 1)
        self.assertIn('You must accept the new terms of use '
                      'to continue logging in', res3.body)

    def test_misconfigured_tou(self):
        faulty_action = deepcopy(DUMMY_ACTION)
        faulty_action['params']['version'] = 'hohoi'
        self.actions_db.add_action(data=faulty_action)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        res1 = self.testapp.get(url)
        self.assertEquals(res1.status, '302 Found')
        res2 = self.testapp.get(res1.location)
        self.assertIn('Missing text for ToU version hohoi '
                      'and lang en', res2.body)
        self.assertEquals(self.actions_db.db_count(), 0)
