"""Live integration with the NetExec (nxc) credential store.

NetExec records results per workspace under ``~/.nxc/workspaces/<workspace>/``,
one SQLite file per protocol (``smb.db``, ``ldap.db``, ``mssql.db`` ...), each
carrying a ``users`` table (``domain``/``username``/``password``/``credtype``).

aliasr treats that store the same way it treats Exegol-history: credentials are
pulled in automatically on startup, and when a credential that came from NetExec
is deleted inside aliasr it is deleted back out of NetExec too (across every
protocol DB). Reads are strictly read-only; the only writes this module makes
are those propagated deletions.
"""

from __future__ import annotations

import configparser
import os
import re
import sqlite3
from collections.abc import Iterable
from pathlib import Path

from aliasr.core.creds import Credential
from aliasr.core.hosts import Host

# An NT hash (32 hex) optionally prefixed with its LM half (``LM:NT``), which is
# how NetExec records ``credtype='hash'`` secrets.
_HASH_RE = re.compile(r"^[0-9a-fA-F]{32}(:[0-9a-fA-F]{32})?$")


# ---------- Locations ----------


def _nxc_home() -> Path:
    """NetExec's home. ``ALIASR_NXC_HOME`` overrides it (tests / non-default installs)."""
    base = os.getenv("ALIASR_NXC_HOME") or "~/.nxc"
    return Path(os.path.expandvars(os.path.expanduser(base)))


def _workspaces_dir() -> Path:
    return _nxc_home() / "workspaces"


def current_workspace() -> str:
    """The workspace NetExec is pointed at (``[nxc] workspace`` in nxc.conf)."""
    conf = _nxc_home() / "nxc.conf"
    try:
        cp = configparser.ConfigParser()
        cp.read(str(conf))
        ws = cp.get("nxc", "workspace", fallback="").strip()
        if ws:
            return ws
    except (configparser.Error, OSError):
        pass
    return "default"


def workspace_dir(workspace: str) -> Path:
    return _workspaces_dir() / workspace


def _protocol_dbs(workspace: str) -> list[Path]:
    """Every protocol database in a workspace (empty if the workspace is absent)."""
    wdir = workspace_dir(workspace)
    return sorted(wdir.glob("*.db")) if wdir.is_dir() else []


# ---------- Mapping ----------


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Column names of ``table`` (empty if the table does not exist)."""
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    except sqlite3.Error:
        return set()


def _nt_from(secret: str) -> str:
    """Pull the NT half out of an ``LM:NT`` (or bare NT) hash, upper-cased."""
    s = secret.strip()
    if ":" in s:
        s = s.rsplit(":", 1)[-1]
    return s.upper()


def _host_fqdn(hostname: str, domain: str) -> str:
    """Build the FQDN aliasr stores as a host's name.

    NetExec keeps the short name and the domain apart (``DC01`` + ``fluffy.htb``);
    aliasr/exegol want the joined FQDN (``DC01.fluffy.htb``). Already-qualified
    names are left as-is.
    """
    hostname = hostname.strip()
    domain = domain.strip()
    if hostname and domain and "." not in hostname:
        return f"{hostname}.{domain}"
    return hostname


def _to_credential(
    domain: str, username: str, secret: str, credtype: str
) -> Credential | None:
    """Map a NetExec users row onto an aliasr :class:`Credential`.

    ``credtype`` decides where the secret lands: ``plaintext`` → password,
    ``hash`` → NT hash. An unlabelled secret is routed by shape so odd exports
    still classify sensibly.
    """
    if not username:
        return None
    password = ""
    nthash = ""
    if credtype == "hash":
        nthash = _nt_from(secret)
    elif credtype == "plaintext":
        password = secret
    elif _HASH_RE.match(secret):
        nthash = _nt_from(secret)
    else:
        password = secret
    return Credential(username=username, password=password, hash=nthash, domain=domain)


# ---------- Public API ----------


def read_creds(workspace: str | None = None) -> list[Credential]:
    """Return the distinct credentials NetExec has for a workspace.

    Users are unioned across every protocol DB (the same account is commonly
    recorded by several protocols) and deduplicated, so the result reflects the
    distinct findings.
    """
    ws = workspace or current_workspace()
    out: list[Credential] = []
    for db in _protocol_dbs(ws):
        try:
            with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
                if "username" not in _columns(conn, "users"):
                    continue
                rows = conn.execute(
                    "SELECT domain, username, password, credtype FROM users"
                ).fetchall()
        except sqlite3.Error:
            continue
        for domain, username, secret, credtype in rows:
            cred = _to_credential(
                domain or "", username or "", secret or "", (credtype or "").lower()
            )
            if cred:
                out.append(cred)

    from aliasr.core.creds import _deduplicate_creds

    return _deduplicate_creds(out)


def read_hosts(workspace: str | None = None) -> list[Host]:
    """Return the distinct hosts NetExec has for a workspace.

    Hosts are unioned across every protocol DB and merged by ip (the same host
    is recorded by several protocols); the short name + domain are joined into
    an FQDN, and a host is tagged ``role="DC"`` when it looks like a domain
    controller -- either ``smb.db``'s ``dc`` flag is set, or the host appears in
    ``ldap.db``. The latter matters because NetExec does not reliably persist
    the ``dc`` flag (a plain ``nxc smb`` run leaves it NULL even when it prints
    ``(DC:True)``), whereas LDAP/389 is a DC-only service in AD, so a row in
    ``ldap.db`` is itself a dependable DC signal.
    """
    ws = workspace or current_workspace()
    meta: dict[str, dict[str, str]] = {}
    dc_ips: set[str] = set()
    for db in _protocol_dbs(ws):
        is_ldap = db.stem == "ldap"
        try:
            with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
                cols = _columns(conn, "hosts")
                if "ip" not in cols:
                    continue
                select = (
                    "ip",
                    "hostname" if "hostname" in cols else "NULL",
                    "domain" if "domain" in cols else "NULL",
                    "dc" if "dc" in cols else "0",
                )
                rows = conn.execute(f"SELECT {', '.join(select)} FROM hosts").fetchall()
        except sqlite3.Error:
            continue
        for ip, hostname, domain, dc in rows:
            if not ip:
                continue
            m = meta.setdefault(ip, {"hostname": "", "domain": ""})
            if hostname and not m["hostname"]:
                m["hostname"] = hostname
            if domain and not m["domain"]:
                m["domain"] = domain
            if dc or is_ldap:
                dc_ips.add(ip)
    return [
        Host(
            ip=ip,
            hostname=_host_fqdn(m["hostname"], m["domain"]),
            role="DC" if ip in dc_ips else "",
        )
        for ip, m in meta.items()
    ]


def delete_creds(keys: Iterable[tuple[str, str]], workspace: str | None = None) -> None:
    """Delete NetExec users rows matching ``(username, domain)`` keys.

    Applied to every protocol DB in the workspace (a user may be recorded by
    more than one protocol). NetExec stores an absent domain as NULL, so the
    match normalises NULL to an empty string. Best-effort: a locked or
    unreadable DB is skipped rather than raising into the caller.
    """
    rows = [(u, d) for (u, d) in keys]
    if not rows:
        return
    ws = workspace or current_workspace()
    for db in _protocol_dbs(ws):
        try:
            with sqlite3.connect(str(db)) as conn:
                if "username" not in _columns(conn, "users"):
                    continue
                conn.executemany(
                    "DELETE FROM users "
                    "WHERE IFNULL(username, '') = ? AND IFNULL(domain, '') = ?",
                    rows,
                )
                conn.commit()
        except sqlite3.Error:
            continue


def delete_hosts(keys: Iterable[tuple[str, str]], workspace: str | None = None) -> None:
    """Delete NetExec hosts rows for the given ``(ip, hostname)`` keys.

    NetExec keys hosts by ip, so the match is on ip alone (the hostname in the
    key is aliasr's FQDN, not NetExec's short name). Applied across every
    protocol DB, best-effort.
    """
    ips = [(ip,) for ip, _ in keys if ip]
    if not ips:
        return
    ws = workspace or current_workspace()
    for db in _protocol_dbs(ws):
        try:
            with sqlite3.connect(str(db)) as conn:
                if "ip" not in _columns(conn, "hosts"):
                    continue
                conn.executemany("DELETE FROM hosts WHERE ip = ?", ips)
                conn.commit()
        except sqlite3.Error:
            continue


def _clear_table(table: str, workspace: str | None) -> None:
    ws = workspace or current_workspace()
    for db in _protocol_dbs(ws):
        try:
            with sqlite3.connect(str(db)) as conn:
                if not _columns(conn, table):
                    continue
                conn.execute(f"DELETE FROM {table}")
                conn.commit()
        except sqlite3.Error:
            continue


def clear_creds(workspace: str | None = None) -> None:
    """Empty the users table in every protocol DB of the workspace (bulk wipe)."""
    _clear_table("users", workspace)


def clear_hosts(workspace: str | None = None) -> None:
    """Empty the hosts table in every protocol DB of the workspace (bulk wipe)."""
    _clear_table("hosts", workspace)
