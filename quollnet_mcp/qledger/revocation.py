"""QLedger-only logout revocation. Never affects other protected resources.

SQLite keeps token fingerprints across worker processes and restarts. All workers
must use the same QLEDGER_LOGOUT_DB_PATH on persistent shared storage.
"""

import os
import sqlite3
from contextlib import closing
from hashlib import sha256
from pathlib import Path
from time import time

from quollnet_mcp.auth import QAuthTokenVerifier


def _database_path() -> Path:
    override = os.getenv("QLEDGER_LOGOUT_DB_PATH")
    if override:
        return Path(override).expanduser()
    state = Path(os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
    return state / "quollnet-mcp" / "qledger-logout.sqlite3"


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5)
    try:
        os.chmod(path, 0o600)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS qledger_revoked ("
            "fingerprint TEXT PRIMARY KEY, expires_at INTEGER NOT NULL)"
        )
        return conn
    except BaseException:
        conn.close()
        raise


def _fingerprint(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def is_revoked(token: str) -> bool:
    with closing(_connect()) as conn:
        return conn.execute(
            "SELECT 1 FROM qledger_revoked WHERE fingerprint=? AND expires_at>?",
            (_fingerprint(token), int(time())),
        ).fetchone() is not None


def revoke(token: str, expires_at: int) -> None:
    now = int(time())
    with closing(_connect()) as conn:
        with conn:
            conn.execute("DELETE FROM qledger_revoked WHERE expires_at<=?", (now,))
            conn.execute(
                "INSERT OR REPLACE INTO qledger_revoked(fingerprint, expires_at) VALUES (?, ?)",
                (_fingerprint(token), max(int(expires_at), now + 1)),
            )


class QLedgerTokenVerifier(QAuthTokenVerifier):
    """Apply QLedger logout after the unchanged shared QAuth signature checks."""

    async def verify_token(self, token: str):
        authorized = await super().verify_token(token)
        if authorized is None:
            return None
        try:
            if is_revoked(token):
                return None
        except (OSError, sqlite3.Error):
            # A failed revocation lookup must not turn into an auth bypass.
            return None
        return authorized
