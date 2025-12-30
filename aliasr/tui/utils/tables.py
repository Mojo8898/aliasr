from rich.table import Table
from rich.padding import Padding
from textual.binding import Binding
from textual.widgets.option_list import Option

from aliasr.core.config import CREDS_MASK, kb_table
from aliasr.core.creds import Credential
from aliasr.core.globals import normalize_key


TABLE_BINDINGS = [
    Binding(
        kb_table("edit_row"),
        "edit_row",
        "Edit",
        priority=True,
        tooltip="Edit the selected row.",
    ),
    Binding(
        kb_table("add_row"),
        "add_row",
        "Add",
        tooltip="Add a new row.",
    ),
    Binding(
        kb_table("delete_row"),
        "delete_row",
        "Delete",
        tooltip="Delete the selected row.",
    ),
    Binding(
        kb_table("move_row_up"),
        "move_row_up",
        "Row Up",
        tooltip="Move the selected row up one.",
    ),
    Binding(
        kb_table("move_row_down"),
        "move_row_down",
        "Row Down",
        tooltip="Move the selected row down one.",
    ),
]


def global_header():
    t = Table(show_header=True, expand=True, pad_edge=False, box=None)
    t.add_column("Global", no_wrap=True, justify="center", ratio=1)
    t.add_column("Value", no_wrap=True, justify="center", ratio=1)
    return Padding(t, (0, 0, 0, 0))


def global_option(key: str, value: str) -> Option:
    t = Table(show_header=False, expand=True, pad_edge=False, box=None)
    t.add_column("global", no_wrap=True, ratio=1)
    t.add_column("value", no_wrap=True, ratio=1)
    t.add_row(normalize_key(key), value)
    return Option(t, id=key)


def _mask(s: str | None) -> str:
    s = s or ""
    return "" if not s else "•" * min(len(s), 32)


def cred_header():
    t = Table(show_header=True, expand=True, pad_edge=False, box=None)
    t.add_column("User", no_wrap=True, justify="center", ratio=1)
    t.add_column("Password", no_wrap=True, justify="center", ratio=1)
    t.add_column("Hash", no_wrap=True, justify="center", ratio=1)
    t.add_column("Domain", no_wrap=True, justify="center", ratio=1)
    return Padding(t, (0, 0, 0, 0))


def cred_option(c: Credential, idx: int) -> Option:
    t = Table(show_header=False, expand=True, pad_edge=False, box=None)
    t.add_column("user", no_wrap=True, ratio=1)
    t.add_column("password", no_wrap=True, ratio=1)
    t.add_column("nt_hash", no_wrap=True, ratio=1)
    t.add_column("domain", no_wrap=True, ratio=1)
    t.add_row(
        c.username,
        _mask(c.password) if CREDS_MASK else c.password,
        _mask(c.hash) if CREDS_MASK else c.hash,
        c.domain,
    )
    return Option(t, id=idx)
