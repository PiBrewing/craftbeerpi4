"""
Login for the endpoints declared with auth_required.

Same behaviour as the SessionTktAuthentication(secret, 60, include_ip=True)
of aiohttp_auth, which this replaces (unmaintained since 2017, as is its
ticket_auth dependency): a login is kept in the aiohttp_session for 60
seconds, bound to the client address, and not renewed. The session cookie
is encrypted, so the ticket needs no signature of its own.
"""
import time
from functools import wraps

from aiohttp import web
from aiohttp_session import get_session

SESSION_KEY = "AUTH_TKT"
MAX_AGE = 60


def _client_ip(request):
    peername = request.transport.get_extra_info("peername") if request.transport else None
    return peername[0] if peername else None


async def remember(request, user_id):
    session = await get_session(request)
    session[SESSION_KEY] = {
        "user": user_id,
        "ip": _client_ip(request),
        "valid_until": int(time.time()) + MAX_AGE,
    }


async def forget(request):
    session = await get_session(request)
    session.pop(SESSION_KEY, None)


async def get_auth(request):
    """The logged in user of the request, or None."""
    session = await get_session(request)
    ticket = session.get(SESSION_KEY)
    if not isinstance(ticket, dict):
        return None
    if ticket.get("ip") != _client_ip(request) or time.time() >= ticket.get("valid_until", 0):
        return None
    return ticket.get("user")


def auth_required(func):
    @wraps(func)
    async def wrapper(*args):
        if await get_auth(args[-1]) is None:
            raise web.HTTPForbidden()
        return await func(*args)

    return wrapper
