"""Host records in the shared Exegol-history database (exh.db `hosts` table).

aliasr models hosts as globals (ip / fqdn / dc_ip / dc_fqdn); this persists the
subset exegol cares about into the shared hosts table so the two tools stay in
sync. Writes upsert on (ip, hostname) and never delete, so hosts added in
exegol are preserved.
"""
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field

from aliasr.core.creds import _db


@dataclass(frozen=True, slots=True)
class Host:
    """A host row, mirroring Exegol-history's `hosts` table."""

    ip: str
    hostname: str
    role: str
    host_id: int | None = field(default=None, compare=False)

    def __iter__(self) -> Iterator[str]:
        return iter([self.ip, self.hostname, self.role])


# (ip, hostname) keys that NetExec supplied this process, captured when its
# hosts are first pulled in. ``None`` means "not pulled yet"; a set (even empty)
# means the pull has run. A key dropped from this set when the user deletes the
# host in aliasr is deleted from NetExec too. Mirrors the creds integration.
_NXC_KEYS: set[tuple[str, str]] | None = None


def _pull_nxc(rows: list[Host]) -> list[Host]:
    """Fold NetExec's hosts into the shared store, once per process.

    NetExec rows are upserted into the shared DB (so they persist and gain
    ids), and their ``(ip, hostname)`` keys are remembered so a later deletion
    in aliasr can propagate back out. A missing NetExec install, or any read
    error, simply yields no hosts.
    """
    global _NXC_KEYS
    if _NXC_KEYS is not None:
        return rows  # already pulled in this process

    _NXC_KEYS = set()
    try:
        from aliasr.core import nxc

        nxc_hosts = nxc.read_hosts()
    except Exception:
        return rows

    _NXC_KEYS = {(h.ip, h.hostname) for h in nxc_hosts}
    if not nxc_hosts:
        return rows

    # Skip the write when everything NetExec has is already stored (the normal
    # launch after the first pull), so startup adds no write to the shared DB.
    existing = {(h.ip, h.hostname, h.role) for h in rows}
    if all((h.ip, h.hostname, h.role) in existing for h in nxc_hosts):
        return rows

    _db.write_hosts(nxc_hosts)  # upsert (never deletes existing rows)
    return _db.read_hosts()


def load_hosts() -> list[Host]:
    """Return every host from the shared database.

    On the first call of a process this also pulls in NetExec's hosts (see
    :func:`_pull_nxc`), so aliasr starts up already carrying them.
    """
    return _pull_nxc(_db.read_hosts())


def save_hosts(hosts: Iterable[Host]) -> None:
    """Upsert hosts into the shared database (never deletes existing rows).

    This is the incremental path used while building a command (it only knows
    about the current target/DC), so it must not delete. The hosts menu uses
    :func:`reconcile_hosts` instead when it needs removals to take effect.
    """
    _db.write_hosts(list(hosts))


def reconcile_hosts(hosts: Iterable[Host]) -> None:
    """Make the hosts table exactly ``hosts`` (the hosts menu's authoritative save).

    Rows carrying a ``host_id`` update in place; id-less rows insert; any stored
    row whose id is absent is deleted. A deleted row that came from NetExec is
    also deleted from NetExec, keeping the two in sync — this is an individual
    deletion, so it always propagates regardless of ``block_bulk_delete``.
    """
    global _NXC_KEYS
    rows = list(hosts)

    if _NXC_KEYS:
        # NetExec keys hosts by ip and delete_hosts matches on ip, so judge
        # presence by ip too. A host whose ip still survives (e.g. its hostname
        # was merely renamed, updating the row in place) is NOT a deletion and
        # must not propagate — matching on (ip, hostname) would wrongly wipe it.
        present_ips = {h.ip for h in rows}
        removed = {(ip, hn) for (ip, hn) in _NXC_KEYS if ip not in present_ips}
        if removed:
            try:
                from aliasr.core import nxc

                nxc.delete_hosts(removed)
            except Exception:
                pass
            _NXC_KEYS -= removed

    _db.reconcile_hosts(rows)


def clear_hosts() -> None:
    """Clear all hosts from the shared database and unset the current host in
    exegol-history's profile.sh, so nothing lingers to autofill from.

    By default this also empties NetExec's hosts (a bulk wipe); setting
    ``[nxc] block_bulk_delete`` leaves NetExec untouched.
    """
    global _NXC_KEYS
    _NXC_KEYS = set()
    _db.clear_hosts()
    from aliasr.core.exegol import clear_current_host

    clear_current_host()

    from aliasr.core.config import NXC_BLOCK_BULK_DELETE

    if not NXC_BLOCK_BULK_DELETE:
        try:
            from aliasr.core import nxc

            nxc.clear_hosts()
        except Exception:
            pass
