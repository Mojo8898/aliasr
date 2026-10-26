"""Bridge to Exegol-history's shell profile (profile.sh).

Exegol-history records the "currently selected" credential and host as
environment variables exported from a profile.sh buffer that Exegol shells
source. We read and write that same file, in the same format exegol uses, so
the current credential and host are shared 1-to-1 between the two tools.

Writing profile.sh cannot change an already-running shell's environment; it
takes effect the next time a shell sources the file -- a new shell, or the
``exec zsh`` that exegol's ``exh`` wrapper performs.
"""
import re
from pathlib import Path
from threading import Lock

from aliasr.core.config import CREDS_PROFILE

# Serializes profile.sh read-modify-write, so concurrent updates (e.g. the
# parallel credential + host clears in `clear all`) don't clobber each other.
_PROFILE_LOCK = Lock()

# Order matches exegol_history.cli.utils.CREDS_VARIABLES / HOSTS_VARIABLES.
_CRED_VARS = ("USER", "PASSWORD", "NT_HASH", "DOMAIN")
_HOST_VARS = ("IP", "TARGET", "DB_HOSTNAME", "DC_HOST", "DC_IP")
_TEMPLATE_VARS = _CRED_VARS + _HOST_VARS

# A variable is "currently set" only on an active (uncommented) export line.
_ACTIVE_RE = re.compile(r"^export\s+([A-Za-z0-9_]+)='(.*)'\s*$")
# Mirrors exegol's VARIABLE_REGEX_UNIX; matches commented template lines too, so
# an update uncomments them exactly as exegol-history does.
_UPDATE_RE = re.compile(r"(?:export|unset) ([\w\d]*)(?:='.*?')?")


def _read_active_vars(path: Path | None) -> dict[str, str]:
    path = path or CREDS_PROFILE
    if not path:
        return {}
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    vals: dict[str, str] = {}
    for line in lines:
        m = _ACTIVE_RE.match(line.strip())
        if m:
            # Reverse the '\'' escaping applied by _write_vars on the way out.
            vals[m.group(1)] = m.group(2).replace("'\\''", "'")
    return vals


def _template_lines() -> list[str]:
    """The commented export template exegol-history seeds a fresh profile.sh with."""
    return [f"#export {v}=''\n" for v in _TEMPLATE_VARS]


def ensure_profile(path: Path | None = None) -> None:
    """Create profile.sh with the commented template if it's missing.

    Mirrors the creds DB being created on first bootstrap access, so a shell
    that sources profile.sh (the ``aliasr init`` / README setup) finds it
    present even before aliasr has set any credential or host.
    """
    path = path or CREDS_PROFILE
    if not path:
        return
    with _PROFILE_LOCK:
        try:
            p = Path(path)
            if p.exists():
                return
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("".join(_template_lines()), encoding="utf-8")
        except OSError:
            pass


def _write_vars(mapping: dict[str, str], path: Path | None) -> None:
    """Update the given exports in profile.sh (value -> export, empty -> unset),
    exactly like exegol-history's parse_and_update."""
    path = path or CREDS_PROFILE
    if not path:
        return
    with _PROFILE_LOCK:
        try:
            p = Path(path)
            if p.exists():
                lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                lines = _template_lines()
            for i, line in enumerate(lines):
                m = _UPDATE_RE.search(line)
                if not m:
                    continue
                name = m.group(1)
                if name in mapping:
                    value = mapping[name]
                    safe = value.replace("'", "'\\''")
                    lines[i] = f"export {name}='{safe}'\n" if value else f"unset {name}\n"
            p.write_text("".join(lines), encoding="utf-8")
        except OSError:
            pass


# ---------- Credentials ----------


def current_credential(path: Path | None = None):
    """Return the credential exegol-history currently has set, or None."""
    vals = _read_active_vars(path)
    if not any(vals.get(v) for v in _CRED_VARS):
        return None
    from aliasr.core.creds import Credential

    return Credential(
        username=vals.get("USER", ""),
        password=vals.get("PASSWORD", ""),
        hash=vals.get("NT_HASH", ""),
        domain=vals.get("DOMAIN", ""),
    )


def set_current_credential(cred, path: Path | None = None) -> None:
    """Write `cred` into profile.sh exactly as exegol-history's `set` does."""
    _write_vars(
        {
            "USER": cred.username,
            "PASSWORD": cred.password,
            "NT_HASH": cred.hash,
            "DOMAIN": cred.domain,
        },
        path,
    )


def clear_current_credential(path: Path | None = None) -> None:
    """Unset the credential variables in profile.sh (mirrors exegol's `unset creds`)."""
    _write_vars({v: "" for v in _CRED_VARS}, path)


# ---------- Hosts ----------


def current_host(path: Path | None = None) -> dict[str, str]:
    """Return exegol-history's current host as aliasr globals, e.g.
    ``{"ip": ..., "fqdn": ..., "dc_ip": ..., "dc_fqdn": ...}`` (set ones only)."""
    vals = _read_active_vars(path)
    out: dict[str, str] = {}
    if vals.get("IP"):
        out["ip"] = vals["IP"]
    if vals.get("DB_HOSTNAME"):
        out["fqdn"] = vals["DB_HOSTNAME"]
    if vals.get("DC_IP"):
        out["dc_ip"] = vals["DC_IP"]
    if vals.get("DC_HOST"):
        out["dc_fqdn"] = vals["DC_HOST"]
    return out


def set_current_host(
    ip: str | None = None,
    fqdn: str | None = None,
    dc_ip: str | None = None,
    dc_fqdn: str | None = None,
    path: Path | None = None,
) -> None:
    """Write host variables into profile.sh the way exegol-history does.

    Only fields passed (not None) are touched, so syncing a target host leaves
    the DC_* variables pinned -- matching exegol's own set-host behavior. ``IP``
    and ``TARGET`` both track the target ip.
    """
    mapping: dict[str, str] = {}
    if ip is not None:
        mapping["IP"] = ip
        mapping["TARGET"] = ip
    if fqdn is not None:
        mapping["DB_HOSTNAME"] = fqdn
    if dc_ip is not None:
        mapping["DC_IP"] = dc_ip
    if dc_fqdn is not None:
        mapping["DC_HOST"] = dc_fqdn
    if mapping:
        _write_vars(mapping, path)


def clear_current_host(path: Path | None = None) -> None:
    """Unset the host variables in profile.sh (mirrors exegol's `unset hosts`)."""
    _write_vars({v: "" for v in _HOST_VARS}, path)
