
from pyramid.security import Allow, Everyone, ALL_PERMISSIONS

from eduid_am.tasks import update_attributes

import logging
logger = logging.getLogger(__name__)


class RootFactory(object):
    __acl__ = [
        (Allow, Everyone, ALL_PERMISSIONS),
    ]

    def __init__(self, request):
        self.request = request

    def propagate_user_changes(self, user):
        update_attributes.delay('eduid_dashboard', str(user['_id']))
