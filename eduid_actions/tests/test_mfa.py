#
# Copyright (c) 2017 NORDUnet A/S
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
        'action': 'mfa',
        'preference': 100, 
        'params': {},
        }


class MFAActionTests(FunctionalTestCase):

    def setUp(self, *args, **kwargs):
        try:
            import eduid_action.mfa
        except ImportError:
            self.skipTest('The MFA plugin is necessary for these tests')
        super(MFAActionTests, self).setUp(*args, **kwargs)

    def test_mfa(self):
        self.actions_db.add_action(data=DUMMY_ACTION)
        # token verification is disabled in the setUp
        # method of FunctionalTestCase
        url = ('/?userid=123467890123456789014567'
                '&token=abc&nonce=sdf&ts=1401093117')
        res1 = self.testapp.get(url)
        self.assertEqual(res1.status, '302 Found')
        res2 = self.testapp.get(res1.location)
        form = res2.forms['mfa-form']
        #self.assertEqual(self.actions_db.db_count(), 1)
        #res3 = form.submit('accept')
        #self.assertEqual(self.actions_db.db_count(), 0)
        #res4 = self.testapp.get(res3.location)
        #self.assertIn(self.settings['idp_url'], res4.location)
