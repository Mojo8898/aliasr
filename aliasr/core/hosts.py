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


def load_hosts() -> list[Host]:
    """Return every host from the shared database."""
    return _db.read_hosts()


def save_hosts(hosts: Iterable[Host]) -> None:
    """Upsert hosts into the shared database (never deletes existing rows)."""
    _db.write_hosts(list(hosts))


def clear_hosts() -> None:
    """Clear all hosts from the shared database and unset the current host in
    exegol-history's profile.sh, so nothing lingers to autofill from."""
    _db.clear_hosts()
    from aliasr.core.exegol import clear_current_host

    clear_current_host()
