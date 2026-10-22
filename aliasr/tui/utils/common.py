import re


_ID_SAFE_RE = re.compile(r"[^0-9A-Za-z_-]")


def widget_id(prefix: str, token: str) -> str:
    """Make a safe, unique-ish widget id from a prefix + token."""
    s = _ID_SAFE_RE.sub("-", (token or "").strip())

    if s[:1].isdigit():
        s = f"n-{s}"

    return f"{prefix}{s}"


def select_value(value) -> str:
    """Normalize a Select's ``.value`` to a plain string ('' when unselected).

    An unset Select is the blank sentinel, not a real option: ``Select.NULL`` on
    Textual 7+, ``Select.BLANK`` on older versions, or ``None``. None of those are
    strings, so treating any non-str as empty is correct across versions and
    avoids comparing against a renamed sentinel.
    """
    return value if isinstance(value, str) else ""
