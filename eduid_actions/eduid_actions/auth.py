from hashlib import sha256
import time

from pyramid.i18n import TranslationString as _

from pyramid.httpexceptions import HTTPForbidden

import logging
logger = logging.getLogger('eduid_actions')


def verify_auth_token(shared_key, userid, token, nonce, timestamp, generator=sha256):
    # check timestamp to make sure it is within 300 seconds from now
    """
    Authenticate user who just logged in in the IdP,
    and has pending actions to perform

    Authentication is done using a shared secret in the configuration of the
    IdP and actions applications.

    :param shared_key: auth_token string from configuration
    :param userid: the identifier of the user
    :param token: authentication token as string
    :param nonce: a public nonce for this authentication request as string
    :param timestamp: unixtime of IdP application as hex string
    :param generator: hash function to use (default: SHA-256)
    :return: bool, True on valid authentication
    """
    logger.debug("Trying to authenticate user {!r} with auth token {!r}".format(userid, token))
    # check timestamp to make sure it is within -300..900 seconds from now
    now = int(time.time())
    ts = int(timestamp, 16)
    if (ts < now - 300) or (ts > now + 900):
        logger.debug("Auth token timestamp {!r} out of bounds ({!s} seconds from {!s})".format(
            timestamp, ts - now, now))
        raise HTTPForbidden(_('Login token expired, please try to log in in the IdP again.'))
    # verify there is a long enough nonce
    if len(nonce) < 16:
        logger.debug("Auth token nonce {!r} too short".format(nonce))
        raise HTTPForbidden(_('Login token invalid'))

    expected = generator("{0}|{1}|{2}|{3}".format(
        shared_key, userid, nonce, timestamp)).hexdigest()
    # constant time comparision of the hash, courtesy of
    # http://rdist.root.org/2009/05/28/timing-attack-in-google-keyczar-library/
    if len(expected) != len(token):
        logger.debug("Auth token bad length")
        raise HTTPForbidden(_('Login token invalid'))
    result = 0
    for x, y in zip(expected, token):
        result |= ord(x) ^ ord(y)
    logger.debug("Auth token match result: {!r}".format(result == 0))
    return result == 0
