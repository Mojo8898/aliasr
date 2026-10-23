"""Backend tests for the SQLite credentials store (Exegol-history exh.db).

These bypass the TUI and drive ``_CredsDB`` directly so the storage contract —
schema compatibility, round-tripping, upsert, and credentials-only clears — is
verified without a human watching the screen. The DB lives in the temp
ALIASR_CREDS_DB set by conftest, so nothing here touches a real exegol DB.
"""

import sqlite3

from aliasr.core.config import CREDS_DB
from aliasr.core.creds import Credential, _db


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(str(CREDS_DB))


def test_schema_is_exegol_compatible():
    _db.write([])  # force-create the DB and tables
    with _conn() as conn:
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        cred_cols = [r[1] for r in conn.execute("PRAGMA table_info(credentials)")]
        host_cols = [r[1] for r in conn.execute("PRAGMA table_info(hosts)")]

    assert {"credentials", "hosts"} <= tables
    assert cred_cols == ["credential_id", "username", "password", "hash", "domain"]
    assert host_cols == ["host_id", "ip", "hostname", "role"]


def test_write_read_roundtrip():
    _db.write(
        [
            Credential("admin", "Pass123!", "", "corp.local"),
            Credential("svc", "", "AAD3BHASH", ""),
        ]
    )
    out = _db.read()

    assert Credential("admin", "Pass123!", "", "corp.local") in out
    # Empty fields are stored as NULL and surface back as "".
    svc = next(c for c in out if c.username == "svc")
    assert svc.password == "" and svc.domain == "" and svc.hash == "AAD3BHASH"


def test_empty_fields_persist_as_null():
    _db.write([Credential("admin", "p", "", "corp.local")])
    with _conn() as conn:
        domain = conn.execute(
            "SELECT domain FROM credentials WHERE username = 'admin'"
        ).fetchone()[0]
    assert domain == "corp.local"

    _db.write([Credential("nobody", "", "", "")])
    with _conn() as conn:
        row = conn.execute(
            "SELECT password, hash, domain FROM credentials WHERE username = 'nobody'"
        ).fetchone()
    assert row == (None, None, None)


def test_upsert_collapses_unique_conflicts():
    # Two rows colliding on (username, domain) — the one constraint exegol
    # enforces — must not raise and must resolve last-write-wins.
    _db.write(
        [
            Credential("dup", "old", "", "d"),
            Credential("dup", "new", "", "d"),
        ]
    )
    rows = [c for c in _db.read() if c.username == "dup"]
    assert len(rows) == 1 and rows[0].password == "new"


def test_read_populates_credential_ids():
    _db.write([Credential("a", "1", "", "d"), Credential("b", "2", "", "d")])
    out = _db.read()
    assert all(c.credential_id is not None for c in out)
    assert len({c.credential_id for c in out}) == len(out)  # unique


def test_edit_in_place_preserves_id():
    _db.write([Credential("admin", "old", "", "corp.local")])
    row = _db.read()[0]
    cid = row.credential_id

    # Same id, changed password -> UPDATE in place, id unchanged.
    _db.write([Credential("admin", "new", "", "corp.local", cid)])
    out = _db.read()
    assert len(out) == 1
    assert out[0].credential_id == cid
    assert out[0].password == "new"


def test_id_tracked_delete_removes_only_the_dropped_row():
    _db.write(
        [
            Credential("keep", "p", "", "d"),
            Credential("drop", "p", "", "d"),
        ]
    )
    rows = _db.read()
    keep = next(c for c in rows if c.username == "keep")
    drop = next(c for c in rows if c.username == "drop")

    # Save back only "keep" (by id) plus a brand-new id-less row.
    _db.write([keep, Credential("fresh", "p", "", "d")])
    out = _db.read()
    names = {c.username for c in out}

    # The dropped row is gone and the retained row kept its original id. (Ids of
    # deleted rows may be reused by new inserts — exegol's schema has no
    # AUTOINCREMENT — so row identity is asserted by content, not by id value.)
    assert names == {"keep", "fresh"}
    assert next(c for c in out if c.username == "keep").credential_id == keep.credential_id
    _ = drop  # dropped row proven absent via `names` above


def test_insert_does_not_disturb_existing_ids():
    _db.write([Credential("a", "1", "", "d")])
    a = _db.read()[0]
    _db.write([a, Credential("b", "2", "", "d")])
    out = {c.username: c.credential_id for c in _db.read()}
    assert out["a"] == a.credential_id


def test_edit_into_collision_resolves_last_write_wins():
    _db.write(
        [
            Credential("admin", "passA", "", "corp.local"),
            Credential("temp", "passB", "", "corp.local"),
        ]
    )
    rows = _db.read()
    temp = next(c for c in rows if c.username == "temp")

    # Rename "temp" onto the existing (admin, corp.local) key.
    _db.write(
        [
            next(c for c in rows if c.username == "admin"),
            Credential("admin", "passB", "", "corp.local", temp.credential_id),
        ]
    )
    out = [c for c in _db.read() if c.domain == "corp.local"]
    assert len(out) == 1  # collapsed, no crash
    assert out[0].username == "admin" and out[0].password == "passB"


def test_clear_only_touches_credentials():
    _db.write([Credential("x", "y", "", "z")])
    with _conn() as conn:
        conn.execute(
            "INSERT INTO hosts (ip, hostname, role) VALUES ('10.0.0.1', 'dc01', 'DC')"
        )
        conn.commit()

    _db.clear()

    with _conn() as conn:
        creds_left = conn.execute("SELECT COUNT(*) FROM credentials").fetchone()[0]
        hosts_left = conn.execute("SELECT COUNT(*) FROM hosts").fetchone()[0]
    assert creds_left == 0
    assert hosts_left == 1  # exegol-owned hosts survive an aliasr creds clear


# ---------- NT hash (MD4 of UTF-16LE) ----------


def test_nt_hash_known_vector():
    """NT hash must match the canonical value for 'password'."""
    from aliasr.core.creds import nt_hash

    assert nt_hash("password") == "8846F7EAEE8FB117AD06BDD830B7586C"


def test_nt_hash_empty_is_blank():
    from aliasr.core.creds import nt_hash

    assert nt_hash("") == ""


def test_nt_hash_uses_md4_fallback_when_hashlib_lacks_it(monkeypatch):
    """OpenSSL 3.x removes legacy md4; nt_hash must still work via pure-Python MD4.

    Regression guard: hashlib.new('md4') raises ValueError on current systems,
    which previously made nt_hash silently return '' (auto-hash did nothing).
    """
    import hashlib

    from aliasr.core import creds

    real_new = hashlib.new

    def no_md4(name, *a, **k):
        if name == "md4":
            raise ValueError("unsupported hash type md4")
        return real_new(name, *a, **k)

    monkeypatch.setattr(hashlib, "new", no_md4)
    assert creds.nt_hash("password") == "8846F7EAEE8FB117AD06BDD830B7586C"


def test_md4_rfc1320_vectors():
    from aliasr.core.creds import _md4

    assert _md4(b"").hex() == "31d6cfe0d16ae931b73c59d7e0c089c0"
    assert _md4(b"abc").hex() == "a448017aaf21d8525fc10ae87aa6729d"


def test_save_materializes_missing_hash():
    """Saving a credential with a password but no hash fills the hash in."""
    from aliasr.core.creds import load_creds, save_creds

    save_creds([Credential("admin", "password", "", "corp.local")])
    stored = {c.username: c for c in load_creds()}
    assert stored["admin"].hash == "8846F7EAEE8FB117AD06BDD830B7586C"
