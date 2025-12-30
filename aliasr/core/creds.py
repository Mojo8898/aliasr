import secrets
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from threading import RLock, Thread
from typing import ClassVar

from aliasr.core.config import CREDS_AUTO_HASH, CREDS_KDBX, CREDS_KEY


@dataclass(frozen=True, slots=True)
class Credential:
    """Credential storage with KeePass integration."""

    GROUP_NAME: ClassVar[str] = "Credentials"
    HASH_PROPERTY: ClassVar[str] = "hash"
    DOMAIN_PROPERTY: ClassVar[str] = "domain"

    username: str
    password: str
    hash: str
    domain: str

    def __iter__(self) -> Iterator[str]:
        return iter([self.username, self.password, self.hash, self.domain])


class _KeePass:
    """Thread-safe KeePass database wrapper."""

    HOSTS_GROUP_NAME = "Hosts"

    def __init__(self) -> None:
        self._kp = None
        self._group = NotImplemented
        self._lock = RLock()

    def _ensure_open(self) -> None:
        """Open KeePass database if not already open."""
        if self._kp is not None:
            return
        if not CREDS_KDBX.exists():
            _ensure_creds()

        from pykeepass import PyKeePass
        self._kp = PyKeePass(str(CREDS_KDBX), keyfile=str(CREDS_KEY))

        # Ensure Credentials group exists
        grp = self._kp.find_groups(name=Credential.GROUP_NAME, first=True)
        if grp is None:
            grp = self._kp.add_group(self._kp.root_group, Credential.GROUP_NAME)

        # Ensure Hosts group exists (for exegol-history compatibility)
        hosts_grp = self._kp.find_groups(name=self.HOSTS_GROUP_NAME, first=True)
        if hosts_grp is None:
            self._kp.add_group(self._kp.root_group, self.HOSTS_GROUP_NAME)

        self._group = grp
        self._kp.save()

    def read(self) -> list[Credential]:
        """List all credentials from KeePass."""
        with self._lock:
            self._ensure_open()
            entries = list(self._group.entries or [])
            return [
                Credential(
                    username=e.username or "",
                    password=e.password or "",
                    hash=e.get_custom_property(Credential.HASH_PROPERTY) or "",
                    domain=e.get_custom_property(Credential.DOMAIN_PROPERTY) or "",
                )
                for e in entries
            ]

    def write(self, creds: Iterable[Credential]) -> None:
        """Write credentials to KeePass (replaces all)."""
        with self._lock:
            self._ensure_open()
            for e in list(self._group.entries or []):
                self._kp.delete_entry(e)

            cid = 1
            written: list[Credential] = []
            for c in creds:
                title = str(cid)
                cid += 1
                e = self._kp.add_entry(
                    self._group, title, c.username or "", c.password or ""
                )
                e.set_custom_property(Credential.HASH_PROPERTY, c.hash, protect=True)
                e.set_custom_property(
                    Credential.DOMAIN_PROPERTY, c.domain, protect=True
                )
                written.append(c)

            self._kp.save()


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

                # Merge c into existing
                result[i] = Credential(
                    username=existing.username or c.username,
                    password=existing.password or c.password,
                    hash=existing.hash or c.hash,
                    domain=existing.domain or c.domain,
                )
                merged = True
                break

        if not merged:
            # Couldn't merge with any existing, add as new
            result.append(c)

    return result


def _ensure_creds() -> None:
    """Ensure credential storage exists (KeePass DB and key file)."""
    CREDS_KDBX.parent.mkdir(parents=True, exist_ok=True)
    CREDS_KEY.parent.mkdir(parents=True, exist_ok=True)

    if not CREDS_KEY.exists():
        CREDS_KEY.write_bytes(secrets.token_bytes(256))

    if not CREDS_KDBX.exists() or CREDS_KDBX.stat().st_size < 1024:
        from pykeepass import create_database
        try:
            create_database(str(CREDS_KDBX), keyfile=str(CREDS_KEY))
        except FileNotFoundError:
            pass


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
_LOADED = False
_kp = _KeePass()


def load_creds() -> list[Credential]:
    """Load credentials with multi-tier caching and deduplication."""
    global _MEMO, _LOADED
    if _MEMO is not None:
        return list(_MEMO)

    if not _LOADED:
        _ensure_creds()
        _LOADED = True

    rows = _kp.read()
    _MEMO = _deduplicate_creds(rows, materialize=False)
    return list(_MEMO)


def save_creds(creds: Iterable[Credential]) -> None:
    """Save credentials to all storage layers, removing duplicates."""
    global _MEMO
    
    unique_creds = _deduplicate_creds(creds, materialize=True)
    _MEMO = list(unique_creds)
    Thread(target=_kp.write, args=(unique_creds,), daemon=False).start()


def clear_creds() -> None:
    """Clear all credentials from all storage layers."""
    global _MEMO
    _MEMO = []
    _kp.write([])
