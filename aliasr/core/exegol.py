"""Bridge to Exegol-history's shell profile (profile.sh).

Exegol-history records the "currently selected" credential as four environment
variables (USER, PASSWORD, NT_HASH, DOMAIN) exported from a profile.sh buffer
that Exegol shells source. We read and write that same file, in the same format
exegol uses, so the current credential is shared 1-to-1 between the two tools.

Writing profile.sh cannot change an already-running shell's environment; it
takes effect the next time a shell sources the file — a new shell, or the
``exec zsh`` that exegol's ``exh`` wrapper performs.
"""
import re
from pathlib import Path

from aliasr.core.config import CREDS_PROFILE

# Order matches exegol_history.cli.utils.CREDS_VARIABLES.
_VARS = ("USER", "PASSWORD", "NT_HASH", "DOMAIN")

# A credential is "currently set" only on an active (uncommented) export line.
_ACTIVE_RE = re.compile(r"^export\s+([A-Za-z0-9_]+)='(.*)'\s*$")
# Mirrors exegol's VARIABLE_REGEX_UNIX; matches commented template lines too, so
# `set` uncomments them exactly as exegol-history does.
_UPDATE_RE = re.compile(r"(?:export|unset) ([\w\d]*)(?:='.*?')?")


def current_credential(path: Path | None = None):
    """Return the credential exegol-history currently has set, or None."""
    path = path or CREDS_PROFILE
    if not path:
        return None
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    vals: dict[str, str] = {}
    for line in lines:
        m = _ACTIVE_RE.match(line.strip())
        if m and m.group(1) in _VARS:
            vals[m.group(1)] = m.group(2)

    if not any(vals.get(v) for v in _VARS):
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
    path = path or CREDS_PROFILE
    if not path:
        return

    mapping = {
        "USER": cred.username,
        "PASSWORD": cred.password,
        "NT_HASH": cred.hash,
        "DOMAIN": cred.domain,
    }
    try:
        p = Path(path)
        if p.exists():
            lines = p.read_text(encoding="utf-8").splitlines(keepends=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            lines = [f"#export {v}=''\n" for v in _VARS]

        for i, line in enumerate(lines):
            m = _UPDATE_RE.search(line)
            if not m:
                continue
            name = m.group(1)
            if name in mapping:
                value = mapping[name]
                lines[i] = f"export {name}='{value}'\n" if value else f"unset {name}\n"

        p.write_text("".join(lines), encoding="utf-8")
    except OSError:
        pass
