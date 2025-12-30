from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Input

from aliasr.tui.utils.grid_nav import GRID_NAV_BINDINGS, grid_nav
from aliasr.core.config import CREDS_AUTO_HASH


class CredEditor(ModalScreen[tuple[str, str, str, str] | None]):
    """Credential editor modal."""

    BINDINGS = [
        Binding("escape", "cancel"),

        *GRID_NAV_BINDINGS,
    ]

    def __init__(self, username: str, password: str, nt_hash: str, domain: str) -> None:
        super().__init__()
        self._username = username
        self._password = password
        self._hash = nt_hash
        self._domain = domain

    # ---------- UI ----------

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static("Credential Editor", id="title")
            with Grid(id="grid"):
                yield Input(
                    value=self._username, placeholder="Enter username...", id="username"
                )
                yield Input(
                    value=self._password,
                    placeholder="Enter password...",
                    id="password",
                )
                yield Input(
                    value=self._hash,
                    placeholder="Enter NT hash...",
                    id="nt-hash",
                )
                yield Input(
                    value=self._domain, placeholder="Enter domain...", id="domain"
                )

    def on_mount(self) -> None:
        for _id in ("#username", "#password", "#nt-hash", "#domain"):
            inp = self.query_one(_id, Input)
            if not (inp.value or "").strip():
                inp.focus()
                return
        self.query_one("#username", Input).focus()

    # ---------- Events ----------

    @on(Input.Changed, "#password")
    def _changed(self, event) -> None:
        """Auto-generate NT hash when password changes."""
        if not CREDS_AUTO_HASH:
            return
        from aliasr.core.creds import nt_hash

        self.query_one("#nt-hash", Input).value = nt_hash(event.value)

    @on(Input.Submitted, "#grid Input")
    def _submit(self, _: Input.Submitted) -> None:
        self.dismiss(
            (
                self.query_one("#username", Input).value,
                self.query_one("#password", Input).value,
                self.query_one("#nt-hash", Input).value,
                self.query_one("#domain", Input).value,
            )
        )

    # ---------- Actions ----------

    def action_grid_nav(self, direction: str) -> None:
        grid_nav(self, direction, grid_selector="#grid", item_selector="Input", cols=2)

    def action_cancel(self) -> None:
        self.dismiss(None)
