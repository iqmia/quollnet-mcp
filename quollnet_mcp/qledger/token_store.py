"""QLedger user/unit token cache scoped to one MCP OAuth access token.

Only this module owns QLedger application credentials. CashflowPot has a wholly
separate implementation. Tokens remain in memory, never in SQLite or tool output.
"""

import asyncio
from collections import OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass, field
from hashlib import sha256
from time import time
from typing import Awaitable, Callable
from weakref import WeakKeyDictionary

import jwt

from .revocation import is_revoked

_MAX_CONNECTIONS = 2048
_MAX_LIFETIME = 3600
_REFRESH_AHEAD = 90


@dataclass
class _Entry:
    subject: str
    app_id: str
    valid_until: float
    user_token: str
    unit_tokens: dict[str, str] = field(default_factory=dict)


_entries: OrderedDict[str, _Entry] = OrderedDict()
_locks: WeakKeyDictionary = WeakKeyDictionary()


def _loop_lock() -> asyncio.Lock:
    """Keep async synchronization bound to its owning event loop."""
    loop = asyncio.get_running_loop()
    lock = _locks.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _locks[loop] = lock
    return lock


_current: ContextVar[tuple[str, str, str] | None] = ContextVar(
    "qledger_connection", default=None
)


def _key(oauth_token: str) -> str:
    return sha256(oauth_token.encode("utf-8")).hexdigest()


def _prune(now: float) -> None:
    for key, entry in list(_entries.items()):
        if entry.valid_until <= now:
            _entries.pop(key, None)
    while len(_entries) > _MAX_CONNECTIONS:
        _entries.popitem(last=False)


def _expires_soon(token: str) -> bool:
    try:
        claims = jwt.decode(
            token,
            options={"verify_signature": False, "verify_exp": False, "verify_aud": False},
        )
        return int(claims["exp"]) <= time() + _REFRESH_AHEAD
    except (jwt.InvalidTokenError, KeyError, ValueError, TypeError):
        # QEntries ultimately validates the token. Some test doubles use opaque values.
        return False


async def _refresh(token: str, callback: Callable[[str], Awaitable[str]]) -> str:
    if not _expires_soon(token):
        return token
    new_token = await callback(token)
    if not new_token:
        raise ValueError("QEntries returned no refreshed token")
    return new_token


def _connection(access, app_id: str) -> tuple[str, float]:
    if access is None or not access.token or not access.subject:
        raise ValueError("Authentication is required")
    if is_revoked(access.token):
        raise ValueError("QLedger is logged out. Reconnect to sign in again.")
    now = time()
    expires = getattr(access, "expires_at", None)
    valid_until = min(float(expires) if expires is not None else now + _MAX_LIFETIME, now + _MAX_LIFETIME)
    if valid_until <= now:
        raise ValueError("QLedger OAuth authorization expired. Reconnect.")
    key = _key(access.token)
    _current.set((key, access.subject, app_id))
    return key, valid_until


async def user_token(
    access,
    app_id: str,
    exchange: Callable[[], Awaitable[str]],
    refresh: Callable[[str], Awaitable[str]],
) -> str:
    key, valid_until = _connection(access, app_id)
    async with _loop_lock():
        _prune(time())
        entry = _entries.get(key)
        if entry is not None and (entry.subject != access.subject or entry.app_id != app_id):
            raise ValueError("QLedger session identity mismatch")
        if entry is None:
            token = await exchange()
            if not token:
                raise ValueError("QAuth returned no QEntries application token")
            # Logout may occur while a network exchange is in progress.
            if is_revoked(access.token):
                raise ValueError("QLedger is logged out. Reconnect.")
            entry = _Entry(access.subject, app_id, valid_until, token)
            _entries[key] = entry
        else:
            entry.user_token = await _refresh(entry.user_token, refresh)
            if is_revoked(access.token):
                raise ValueError("QLedger is logged out. Reconnect.")
        _entries.move_to_end(key)
        _prune(time())
        return entry.user_token


async def unit_token(
    access,
    app_id: str,
    unit_id: str,
    exchange: Callable[[], Awaitable[str]],
    refresh: Callable[[str], Awaitable[str]],
    load: Callable[[str, str], Awaitable[str]],
) -> str:
    await user_token(access, app_id, exchange, refresh)
    key, _ = _connection(access, app_id)
    async with _loop_lock():
        entry = _entries.get(key)
        if entry is None:
            raise ValueError("QLedger session expired")
        token = entry.unit_tokens.get(unit_id)
        if token is None:
            token = await load(entry.user_token, unit_id)
            if not token:
                raise ValueError("QEntries returned no unit token")
        else:
            token = await _refresh(token, refresh)
        if is_revoked(access.token):
            raise ValueError("QLedger is logged out. Reconnect.")
        entry.unit_tokens[unit_id] = token
        _entries.move_to_end(key)
        return token


async def remember_unit_token(token: str, unit_id: str) -> None:
    connection = _current.get()
    if connection is None:
        return
    key, subject, app_id = connection
    async with _loop_lock():
        entry = _entries.get(key)
        if entry and entry.subject == subject and entry.app_id == app_id and entry.valid_until > time():
            entry.unit_tokens[unit_id] = token
            _entries.move_to_end(key)


async def forget(oauth_token: str) -> None:
    async with _loop_lock():
        _entries.pop(_key(oauth_token), None)
