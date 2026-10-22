import sqlite3
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from threading import RLock, Thread

from aliasr.core.config import CREDS_AUTO_HASH, CREDS_DB


@dataclass(frozen=True, slots=True)
class Credential:
    """A single credential row, mirroring Exegol-history's `credentials` table.

    ``credential_id`` is the primary key of the backing row (``None`` for a
    credential that has not been persisted yet). It is storage metadata, not
    identity, so it is excluded from equality/hashing — two credentials with the
    same fields compare equal regardless of id.
    """

    username: str
    password: str
    hash: str
    domain: str
    credential_id: int | None = field(default=None, compare=False)

    def __iter__(self) -> Iterator[str]:
        return iter([self.username, self.password, self.hash, self.domain])


# DDL mirrors exactly what Exegol-history's SQLAlchemy models emit (verified
# against v3.1), so both tools can share the same database (default
# ~/.exegol_history/exh.db). The single-column INTEGER PRIMARY KEY is a rowid
# alias, so inserts without an explicit id auto-assign one, matching Exegol.
# See ThePorgs/Exegol-history db_api/creds.py and db_api/hosts.py.
_CREDENTIALS_DDL = """
CREATE TABLE IF NOT EXISTS credentials (
    credential_id INTEGER NOT NULL,
    username VARCHAR,
    password VARCHAR,
    hash VARCHAR,
    domain VARCHAR,
    PRIMARY KEY (credential_id),
    UNIQUE (username, domain)
)
"""

_HOSTS_DDL = """
CREATE TABLE IF NOT EXISTS hosts (
    host_id INTEGER NOT NULL,
    ip VARCHAR,
    hostname VARCHAR,
    role VARCHAR,
    PRIMARY KEY (host_id),
    UNIQUE (ip, hostname)
)
"""


class _CredsDB:
    """Thread-safe wrapper over the shared SQLite credentials store."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._ready = False

    def _ensure_db(self) -> None:
        """Create the database file and Exegol-compatible tables if missing."""
        if self._ready and CREDS_DB.exists():
            return
        CREDS_DB.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(CREDS_DB)) as conn:
            conn.execute(_CREDENTIALS_DDL)
            conn.execute(_HOSTS_DDL)
            conn.commit()
        self._ready = True

    def _connect(self) -> sqlite3.Connection:
        self._ensure_db()
        return sqlite3.connect(str(CREDS_DB))

    def read(self) -> list[Credential]:
        """Return every credential, oldest first (NULLs surfaced as empty strings)."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT credential_id, username, password, hash, domain "
                    "FROM credentials ORDER BY credential_id"
                ).fetchall()
        return [
            Credential(
                username=r[1] or "",
                password=r[2] or "",
                hash=r[3] or "",
                domain=r[4] or "",
                credential_id=r[0],
            )
            for r in rows
        ]

    def write(self, creds: Iterable[Credential]) -> None:
        """Reconcile the credentials table against `creds` incrementally.

        Rows carrying a ``credential_id`` are updated in place (so Exegol keeps
        seeing stable primary keys); id-less rows are inserted. Any stored row
        whose id is absent from the incoming set is deleted — an id-tracked
        delete — while the hosts table is never touched. New inserts merge into an
        existing row on the (username, domain) constraint Exegol enforces.
        """
        rows = list(creds)
        keep_ids = [c.credential_id for c in rows if c.credential_id is not None]
        with self._lock:
            with self._connect() as conn:
                if keep_ids:
                    placeholders = ",".join("?" * len(keep_ids))
                    conn.execute(
                        "DELETE FROM credentials "
                        f"WHERE credential_id NOT IN ({placeholders})",
                        keep_ids,
                    )
                else:
                    conn.execute("DELETE FROM credentials")
                for c in rows:
                    self._upsert(conn, c)
                conn.commit()

    def _upsert(self, conn: sqlite3.Connection, c: Credential) -> None:
        """Update the row with c's id, else insert (merging on username/domain)."""
        values = (
            c.username or None,
            c.password or None,
            c.hash or None,
            c.domain or None,
        )
        if c.credential_id is not None:
            try:
                cur = conn.execute(
                    "UPDATE credentials SET username=?, password=?, hash=?, domain=? "
                    "WHERE credential_id=?",
                    (*values, c.credential_id),
                )
                if cur.rowcount:
                    return
            except sqlite3.IntegrityError:
                # Edited into a collision on (username, domain): last-write-wins —
                # drop the row it now duplicates, then apply the edit.
                conn.execute(
                    "DELETE FROM credentials "
                    "WHERE username IS ? AND domain IS ? AND credential_id != ?",
                    (values[0], values[3], c.credential_id),
                )
                conn.execute(
                    "UPDATE credentials SET username=?, password=?, hash=?, domain=? "
                    "WHERE credential_id=?",
                    (*values, c.credential_id),
                )
                return
        # New row (or a stale id that no longer exists): insert, merging on conflict.
        conn.execute(
            "INSERT INTO credentials (username, password, hash, domain) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(username, domain) DO UPDATE SET "
            "password=excluded.password, hash=excluded.hash",
            values,
        )

    def clear(self) -> None:
        """Delete all credentials (leaves the hosts table intact)."""
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM credentials")
                conn.commit()


# ---------- Helpers ----------


def _materialize_hash(c: Credential) -> Credential:
    """Generate NT hash if configured and missing."""
    if not CREDS_AUTO_HASH:
        return c

    if c.hash.strip() or not c.password.strip():
        return c

    return Credential(
        username=c.username,
        password=c.password,
        hash=nt_hash(c.password),
        domain=c.domain,
        credential_id=c.credential_id,
    )



def _deduplicate_creds(creds: Iterable[Credential], materialize: bool = False) -> list[Credential]:
    """Deduplicate credentials by merging those with matching non-empty fields."""
    result = []

    for c in creds:
        # Apply hash materialization if requested
        if materialize:
            c = _materialize_hash(c)

        # Try to merge with an existing credential
        merged = False
        for i, existing in enumerate(result):
            # Check if c can be merged with existing (no conflicts)
            if (not (existing.username and c.username and existing.username != c.username) and
                not (existing.password and c.password and existing.password != c.password) and
                not (existing.hash and c.hash and existing.hash != c.hash) and
                not (existing.domain and c.domain and existing.domain != c.domain)):

                # Merge c into existing (keep whichever id is already persisted)
                result[i] = Credential(
                    username=existing.username or c.username,
                    password=existing.password or c.password,
                    hash=existing.hash or c.hash,
                    domain=existing.domain or c.domain,
                    credential_id=existing.credential_id or c.credential_id,
                )
                merged = True
                break

        if not merged:
            # Couldn't merge with any existing, add as new
            result.append(c)

    return result


# ---------- Public API ----------


def nt_hash(password: str) -> str:
    """Generate NT hash from password."""
    if not password:
        return ""

    import hashlib
    try:
        return hashlib.new("md4", password.encode("utf-16le")).hexdigest().upper()
    except Exception:
        return ""


_MEMO: list[Credential] | None = None
_db = _CredsDB()


def load_creds() -> list[Credential]:
    """Load credentials with memoization and deduplication."""
    global _MEMO
    if _MEMO is not None:
        return list(_MEMO)

    rows = _db.read()
    _MEMO = _deduplicate_creds(rows, materialize=False)
    return list(_MEMO)


def save_creds(creds: Iterable[Credential]) -> None:
    """Save credentials to storage, removing duplicates."""
    global _MEMO

    unique_creds = _deduplicate_creds(creds, materialize=True)
    _MEMO = list(unique_creds)
    Thread(target=_db.write, args=(unique_creds,), daemon=False).start()


def clear_creds() -> None:
    """Clear all credentials from storage."""
    global _MEMO
    _MEMO = []
    _db.clear()
