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


class _ExhDB:
    """Thread-safe wrapper over the shared SQLite store (credentials + hosts)."""

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

    def read_hosts(self) -> list:
        """Return every host, oldest first (NULLs surfaced as empty strings)."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT host_id, ip, hostname, role FROM hosts ORDER BY host_id"
                ).fetchall()
        from aliasr.core.hosts import Host

        return [
            Host(ip=r[1] or "", hostname=r[2] or "", role=r[3] or "", host_id=r[0])
            for r in rows
        ]

    def write_hosts(self, hosts) -> None:
        """Upsert hosts on (ip, hostname); never deletes, so exegol-added hosts
        and the credentials table are left intact."""
        payload = [
            (h.ip or None, h.hostname or None, h.role or None)
            for h in hosts
            if (h.ip or h.hostname)
        ]
        if not payload:
            return
        with self._lock:
            with self._connect() as conn:
                conn.executemany(
                    "INSERT INTO hosts (ip, hostname, role) VALUES (?, ?, ?) "
                    "ON CONFLICT(ip, hostname) DO UPDATE SET role=excluded.role",
                    payload,
                )
                conn.commit()

    def reconcile_hosts(self, hosts) -> None:
        """Reconcile the hosts table to exactly `hosts` (id-tracked delete).

        Rows carrying a ``host_id`` update in place; id-less rows insert
        (merging on the (ip, hostname) constraint); any stored row whose id is
        absent from the incoming set is deleted. Unlike :meth:`write_hosts` this
        removes, so it backs the hosts menu where deletions must stick. The
        credentials table is never touched.
        """
        rows = [h for h in hosts if (h.ip or h.hostname)]
        keep_ids = [h.host_id for h in rows if h.host_id is not None]
        with self._lock:
            with self._connect() as conn:
                if keep_ids:
                    placeholders = ",".join("?" * len(keep_ids))
                    conn.execute(
                        f"DELETE FROM hosts WHERE host_id NOT IN ({placeholders})",
                        keep_ids,
                    )
                else:
                    conn.execute("DELETE FROM hosts")
                for h in rows:
                    payload = (h.ip or None, h.hostname or None, h.role or None)
                    if h.host_id is not None:
                        cur = conn.execute(
                            "UPDATE hosts SET ip=?, hostname=?, role=? WHERE host_id=?",
                            (*payload, h.host_id),
                        )
                        if cur.rowcount:
                            continue
                    conn.execute(
                        "INSERT INTO hosts (ip, hostname, role) VALUES (?, ?, ?) "
                        "ON CONFLICT(ip, hostname) DO UPDATE SET role=excluded.role",
                        payload,
                    )
                conn.commit()

    def clear_hosts(self) -> None:
        """Delete all hosts (leaves the credentials table intact)."""
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM hosts")
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


def _md4(data: bytes) -> bytes:
    """Pure-Python MD4 (RFC 1320).

    Used for NT hashes when the platform's hashlib lacks the legacy ``md4``
    algorithm — OpenSSL 3.x disables it by default, so ``hashlib.new("md4")``
    raises ``ValueError`` on most current systems.
    """
    import struct

    def rol(x: int, n: int) -> int:
        x &= 0xFFFFFFFF
        return ((x << n) | (x >> (32 - n))) & 0xFFFFFFFF

    a, b, c, d = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476
    msg = bytearray(data)
    bit_len = (len(data) * 8) & 0xFFFFFFFFFFFFFFFF
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0)
    msg += struct.pack("<Q", bit_len)

    for off in range(0, len(msg), 64):
        X = list(struct.unpack("<16I", msg[off:off + 64]))
        aa, bb, cc, dd = a, b, c, d
        for i in (0, 4, 8, 12):  # round 1
            a = rol(a + ((b & c) | (~b & d)) + X[i], 3)
            d = rol(d + ((a & b) | (~a & c)) + X[i + 1], 7)
            c = rol(c + ((d & a) | (~d & b)) + X[i + 2], 11)
            b = rol(b + ((c & d) | (~c & a)) + X[i + 3], 19)
        for i in (0, 1, 2, 3):  # round 2
            a = rol(a + ((b & c) | (b & d) | (c & d)) + X[i] + 0x5A827999, 3)
            d = rol(d + ((a & b) | (a & c) | (b & c)) + X[i + 4] + 0x5A827999, 5)
            c = rol(c + ((d & a) | (d & b) | (a & b)) + X[i + 8] + 0x5A827999, 9)
            b = rol(b + ((c & d) | (c & a) | (d & a)) + X[i + 12] + 0x5A827999, 13)
        for i in (0, 2, 1, 3):  # round 3
            a = rol(a + (b ^ c ^ d) + X[i] + 0x6ED9EBA1, 3)
            d = rol(d + (a ^ b ^ c) + X[i + 8] + 0x6ED9EBA1, 9)
            c = rol(c + (d ^ a ^ b) + X[i + 4] + 0x6ED9EBA1, 11)
            b = rol(b + (c ^ d ^ a) + X[i + 12] + 0x6ED9EBA1, 15)
        a = (a + aa) & 0xFFFFFFFF
        b = (b + bb) & 0xFFFFFFFF
        c = (c + cc) & 0xFFFFFFFF
        d = (d + dd) & 0xFFFFFFFF

    return struct.pack("<4I", a, b, c, d)


def nt_hash(password: str) -> str:
    """Generate the NT hash (MD4 of the UTF-16LE password) as upper-hex."""
    if not password:
        return ""

    data = password.encode("utf-16le")
    import hashlib
    try:
        return hashlib.new("md4", data).hexdigest().upper()
    except ValueError:
        # Legacy md4 unavailable (OpenSSL 3.x) — fall back to pure Python.
        return _md4(data).hex().upper()
    except Exception:
        return ""


_MEMO: list[Credential] | None = None

# (username, domain) keys that NetExec supplied this process, captured when its
# credentials are first pulled in. ``None`` means "not pulled yet"; a set (even
# empty) means the pull has run. A key dropped from this set when the user
# deletes the credential in aliasr is deleted from NetExec too.
_NXC_KEYS: set[tuple[str, str]] | None = None

_db = _ExhDB()


def _pull_nxc(rows: list[Credential]) -> list[Credential]:
    """Fold NetExec's credentials into the shared store, once per process.

    NetExec rows are written into the shared DB (so they gain stable ids and
    persist like any other credential), and their ``(username, domain)`` keys
    are remembered so a later deletion in aliasr can propagate back out. A
    missing NetExec install, or any read error, simply yields no credentials.
    """
    global _NXC_KEYS
    if _NXC_KEYS is not None:
        return rows  # already pulled in this process

    _NXC_KEYS = set()
    try:
        from aliasr.core import nxc

        nxc_creds = [_materialize_hash(c) for c in nxc.read_creds()]
    except Exception:
        return rows

    _NXC_KEYS = {(c.username, c.domain) for c in nxc_creds}
    if not nxc_creds:
        return rows

    merged = _deduplicate_creds(list(rows) + nxc_creds, materialize=False)

    # Only touch the shared DB when the pull actually changes it. On a normal
    # launch NetExec's creds are already persisted, so the merge equals what's
    # on disk and we skip the write entirely — no extra I/O or lock contention
    # on the database Exegol also shares.
    def _sig(cs: list[Credential]):
        return sorted((c.username, c.password, c.hash, c.domain) for c in cs)

    if _sig(merged) == _sig(rows):
        return merged

    # Persist (existing rows keep their ids; NetExec rows insert, merging on the
    # (username, domain) constraint), then re-read so everything carries an id.
    _db.write(merged)
    return _db.read()


def _nxc_key_covered(key: tuple[str, str], creds: list[Credential]) -> bool:
    """Is a NetExec ``(username, domain)`` still represented in ``creds``?

    Deduplication can merge a NetExec row into an existing one and shift its
    domain (e.g. NetExec's ``admin``/``""`` folds into ``admin``/``CORP``), so a
    plain key-set diff would wrongly flag the NetExec key as deleted the next
    time anything is saved. A key counts as still present when some credential
    shares its username and a compatible domain (equal, or empty on either
    side) — matching how the two would have merged.
    """
    u, d = key
    return any(
        c.username == u and (not d or not c.domain or c.domain == d) for c in creds
    )


def load_creds() -> list[Credential]:
    """Load credentials with memoization and deduplication.

    On the first call of a process this also pulls in NetExec's credentials
    (see :func:`_pull_nxc`), so aliasr starts up already carrying whatever
    NetExec has discovered.
    """
    global _MEMO
    if _MEMO is not None:
        return list(_MEMO)

    rows = _pull_nxc(_db.read())
    _MEMO = _deduplicate_creds(rows, materialize=False)
    return list(_MEMO)


def save_creds(creds: Iterable[Credential]) -> None:
    """Save credentials to storage, removing duplicates.

    Any NetExec-sourced credential no longer present in ``creds`` (i.e. deleted
    in aliasr) is also deleted from the NetExec database, keeping the two stores
    in sync the way aliasr already does with Exegol-history.
    """
    global _MEMO, _NXC_KEYS

    unique_creds = _deduplicate_creds(creds, materialize=True)

    if _NXC_KEYS:
        removed = {k for k in _NXC_KEYS if not _nxc_key_covered(k, unique_creds)}
        if removed:
            try:
                from aliasr.core import nxc

                nxc.delete_creds(removed)
            except Exception:
                pass
            _NXC_KEYS -= removed

    _MEMO = list(unique_creds)
    Thread(target=_db.write, args=(unique_creds,), daemon=False).start()


def has_stored_creds() -> bool:
    """Whether the shared store currently holds any credential (no NetExec pull)."""
    return bool(_db.read())


def clear_creds() -> bool:
    """Clear all credentials from storage and unset the current credential in
    exegol-history's profile.sh, so nothing lingers to autofill from.

    By default this also empties NetExec's credential store (a bulk wipe), so
    ``aliasr clear creds`` clears both. Setting ``[nxc] block_bulk_delete`` in
    the config forbids that bulk deletion, leaving NetExec untouched. Either
    way the NetExec keys are forgotten so the wipe isn't later misread as a
    batch of individual deletions on the next save.

    Returns True if anything was actually removed (aliasr store or, when not
    blocked, NetExec), else False.
    """
    global _MEMO, _NXC_KEYS
    from aliasr.core.config import NXC_BLOCK_BULK_DELETE

    changed = bool(_db.read())
    _MEMO = []
    _NXC_KEYS = set()
    _db.clear()

    if not NXC_BLOCK_BULK_DELETE:
        try:
            from aliasr.core import nxc

            if not changed and nxc.read_creds():
                changed = True
            nxc.clear_creds()
        except Exception:
            pass
    from aliasr.core.exegol import clear_current_credential

    clear_current_credential()
    return changed
