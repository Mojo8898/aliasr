from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Vertical
from textual.screen import ModalScreen
from textual.widgets import Static, Input

from aliasr.tui.utils.grid_nav import GRID_NAV_BINDINGS, grid_nav


class HostEditor(ModalScreen[tuple[str, str, str] | None]):
    """Host editor modal (ip / hostname / role)."""

    BINDINGS = [
        Binding("escape", "cancel"),

        *GRID_NAV_BINDINGS,
    ]

    def __init__(self, ip: str, hostname: str, role: str) -> None:
        super().__init__()
        self._ip = ip
        self._hostname = hostname
        self._role = role

    # ---------- UI ----------

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static("Host Editor", id="title")
            with Grid(id="grid"):
                yield Input(value=self._ip, placeholder="Enter IP...", id="ip")
                yield Input(
                    value=self._hostname, placeholder="Enter hostname/FQDN...", id="hostname"
                )
                yield Input(
                    value=self._role, placeholder="Enter role (e.g. DC)...", id="role"
                )

    def on_mount(self) -> None:
        for _id in ("#ip", "#hostname", "#role"):
            inp = self.query_one(_id, Input)
            if not (inp.value or "").strip():
                inp.focus()
                return
        self.query_one("#ip", Input).focus()

    # ---------- Events ----------

    @on(Input.Submitted, "#grid Input")
    def _submit(self, _: Input.Submitted) -> None:
        self.dismiss(
            (
                self.query_one("#ip", Input).value,
                self.query_one("#hostname", Input).value,
                self.query_one("#role", Input).value,
            )
        )

    # ---------- Actions ----------

    def action_grid_nav(self, direction: str) -> None:
        grid_nav(self, direction, grid_selector="#grid", item_selector="Input", cols=2)

    def action_cancel(self) -> None:
        self.dismiss(None)
