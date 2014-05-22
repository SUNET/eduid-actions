from eduid_actions.testing import FunctionalTestCase


class HomeViewTests(FunctionalTestCase):

    def test_home(self):
        res = self.testapp.get('/')
        self.assertEqual(res.status, '200 OK')
        self.assertIn('Home', res.body)
