import re


_ID_SAFE_RE = re.compile(r"[^0-9A-Za-z_-]")


def widget_id(prefix: str, token: str) -> str:
    """Make a safe, unique-ish widget id from a prefix + token."""
    s = _ID_SAFE_RE.sub("-", (token or "").strip())

    if s[:1].isdigit():
        s = f"n-{s}"

    return f"{prefix}{s}"
