from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Static

from aliasr.core.config import kb_root
from aliasr.core.globals import normalize_key
from aliasr.tui.utils.grid_nav import GRID_NAV_BINDINGS, grid_nav
from aliasr.tui.utils.smart_complete import SmartComplete


class ValueInput(Input):
    BINDINGS = [
        Binding(
            kb_root("tree_screen"),
            "open_tree_screen",
            "Tree",
            tooltip="Open the tree menu for the currently focused value.",
        ),
    ]

    def action_open_tree_screen(self) -> None:
        def _done(result: str | None) -> None:
            if result is None:
                return
            self.value = result
            self.action_select_all()
            self.focus()

        from aliasr.tui.tree_screen import TreeScreen
        self.app.push_screen(TreeScreen(), _done)


class NewGlobal(ModalScreen[tuple[str, str] | None]):
    """Add a new global; returns (key, value) or None."""

    BINDINGS = [
        Binding("escape", "cancel"),

        *GRID_NAV_BINDINGS,
        Binding("pageup", "sc_page_up"),
        Binding("pagedown", "sc_page_down"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static("New Global", id="title")
            with Grid(id="grid"):
                yield Input(placeholder="Enter new global key...", id="key")
                value_input = ValueInput(placeholder="Enter new global value...", id="value")
                yield value_input

            yield SmartComplete(target=value_input, id="value-complete")
            yield Footer()

    def on_mount(self) -> None:
        key = self.query_one("#key", Input)
        val = self.query_one("#value", Input)
        key.border_title = "Key"
        val.border_title = "Value"
        key.focus()

    # ---------- Helpers ----------

    def _get_smart_complete(self) -> SmartComplete | None:
        """Get the SmartComplete widget if it exists."""
        try:
            return self.query_one("#value-complete", SmartComplete)
        except Exception:
            return None

    def _is_dropdown_visible(self) -> bool:
        """Check if SmartComplete dropdown is visible."""
        sc = self._get_smart_complete()
        return sc.is_dropdown_visible if sc else False

    # ---------- Actions ----------

    def action_grid_nav(self, direction: str) -> None:
        if self._is_dropdown_visible() and direction in ("up", "down"):
            sc = self._get_smart_complete()
            if sc:
                if direction == "up":
                    sc.option_list.action_cursor_up()
                else:
                    sc.option_list.action_cursor_down()
            return
        
        grid_nav(self, direction, grid_selector="#grid", item_selector="Input", cols=2)

    def action_sc_page_up(self) -> None:
        """Route page up to SmartComplete if dropdown is visible."""
        if self._is_dropdown_visible():
            sc = self._get_smart_complete()
            if sc:
                sc.option_list.action_page_up()

    def action_sc_page_down(self) -> None:
        """Route page down to SmartComplete if dropdown is visible."""
        if self._is_dropdown_visible():
            sc = self._get_smart_complete()
            if sc:
                sc.option_list.action_page_down()

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Input.Submitted, "#key,#value")
    def _submit(self, _: Input.Submitted) -> None:
        key_inp = self.query_one("#key", Input)
        val_inp = self.query_one("#value", Input)
        key = normalize_key((key_inp.value or "").strip())
        if not key:
            key_inp.focus()
            return
        self.dismiss((key, (val_inp.value or "").strip()))
