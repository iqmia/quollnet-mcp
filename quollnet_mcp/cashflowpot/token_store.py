"""Request-scoped CashflowPot token handoff for the dedicated MCP resource.

The external MCP OAuth token stays with ChatGPT. On the first request for that
OAuth access token, QAuth exchanges it for an ordinary CashflowPot app token.
Afterwards the MCP forwards its latest app/Unit token to q_flow; q_flow remains
responsible for authorization, Unit loading and refresh.

This is an in-process, bounded cache. A second worker or a restart can perform
its own initial exchange. Cache keys are fingerprints of the MCP bearer token,
not bearer tokens themselves, and never cross OAuth connections.
"""

import asyncio
from collections import OrderedDict
from contextvars import ContextVar
from dataclasses import dataclass
from hashlib import sha256
from time import time
from typing import Awaitable, Callable

import jwt

_MAX_CONNECTIONS = 2048
_MAX_LIFETIME_SECONDS = 3600


@dataclass
class _CachedToken:
    value: str
    app_token: str
    subject: str
    app_id: str
    valid_until: float


_tokens: OrderedDict[str, _CachedToken] = OrderedDict()
_exchange_lock = asyncio.Lock()
_current_connection: ContextVar[tuple[str, str, str] | None] = ContextVar(
    "cashflowpot_mcp_connection", default=None
)


def _prune(now: float) -> None:
    for key, entry in list(_tokens.items()):
        if entry.valid_until <= now:
            _tokens.pop(key, None)
    while len(_tokens) > _MAX_CONNECTIONS:
        _tokens.popitem(last=False)


async def get_cashflowpot_app_token(
    *,
    oauth_token: str,
    subject: str,
    app_id: str,
    oauth_expires_at: int | None,
    exchange: Callable[[], Awaitable[str]],
    prefer_app_token: bool = False,
) -> str:
    """Reuse the app token for this OAuth connection, exchanging on cache miss.

    q_flow handles moving from an application token to a Unit token and returns
    any updated token in the same API response. No Unit token exchange is
    initiated directly from the MCP. General operations can choose the saved
    app token, even when the latest token is Unit-scoped.
    """
    key = sha256(oauth_token.encode("utf-8")).hexdigest()
    _current_connection.set((key, subject, app_id))
    now = time()
    valid_until = min(
        float(oauth_expires_at) if oauth_expires_at is not None else now + _MAX_LIFETIME_SECONDS,
        now + _MAX_LIFETIME_SECONDS,
    )
    if valid_until <= now:
        raise ValueError("The MCP OAuth token has expired")

    # Also protects simultaneous first requests for a single connection from
    # performing duplicate QAuth exchanges.
    async with _exchange_lock:
        _prune(now)
        cached = _tokens.get(key)
        if (
            cached is not None
            and cached.subject == subject
            and cached.app_id == app_id
            and cached.valid_until > now
        ):
            _tokens.move_to_end(key)
            return cached.app_token if prefer_app_token else cached.value

        token = await exchange()
        _tokens[key] = _CachedToken(
            value=token, app_token=token, subject=subject, app_id=app_id, valid_until=valid_until,
        )
        _tokens.move_to_end(key)
        _prune(time())
        return token


def accept_cashflowpot_token_from_qflow(
    *, sent_token: str, replacement_token: str | None,
) -> bool:
    """Adopt q_flow's returned token, without allowing stale concurrent writes.

    The decoded claims check only guards against accidental identity crossover.
    Authentication still belongs to q_flow (which validates the JWT signature).
    Only tokens coming from the authenticated q_flow HTTPS response reach here.
    """
    connection = _current_connection.get()
    if connection is None or not isinstance(replacement_token, str):
        return False
    replacement = replacement_token.strip()
    if replacement.lower().startswith("bearer "):
        replacement = replacement[7:].strip()
    if not replacement:
        return False

    key, subject, app_id = connection
    cached = _tokens.get(key)
    if (
        cached is None
        or cached.subject != subject
        or cached.app_id != app_id
        or cached.valid_until <= time()
        or (cached.value != sent_token and cached.app_token != sent_token)
    ):
        return False
    if replacement == sent_token:
        return False

    try:
        claims = jwt.decode(
            replacement,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
            },
        )
    except (jwt.InvalidTokenError, ValueError, TypeError):
        return False

    if (
        claims.get("user_id") != subject
        or claims.get("client_app_id") != app_id
        or claims.get("aud") != app_id
    ):
        return False
    expires_at = claims.get("exp")
    if not isinstance(expires_at, (int, float)) or expires_at <= time():
        return False

    # No await between compare and replacement: safe against concurrent
    # requests in this event loop. Late responses cannot undo newer tokens.
    # Preserve the general app token for list/create/restore operations even
    # after q_flow moves the active token into a specific Unit. An updated
    # user token replaces the app token; a Unit token never does.
    if not claims.get("unit_id"):
        cached.app_token = replacement
    if cached.value == sent_token:
        cached.value = replacement
    _tokens.move_to_end(key)
    return True
