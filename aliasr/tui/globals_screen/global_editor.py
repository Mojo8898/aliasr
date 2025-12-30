from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, Static

from aliasr.core.config import GLOBALS_HISTORY, kb_root, kb_table
from aliasr.tui.utils.smart_complete import SmartComplete


class GlobalEditor(ModalScreen[str | None]):
    """Edit a single global value with simple history navigation."""

    BINDINGS = [
        Binding("escape", "cancel"),
        Binding(kb_root("globals_editor"), "cancel"),

        Binding("up", "cursor_up"),
        Binding("down", "cursor_down"),
        Binding("pageup", "page_up"),
        Binding("pagedown", "page_down"),

        Binding(
            kb_table("delete_row"),
            "delete_row",
            "Delete",
        ),
        Binding(
            kb_table("move_row_up"),
            "move_row_up",
            "Row Up",
            show=GLOBALS_HISTORY,
        ),
        Binding(
            kb_table("move_row_down"),
            "move_row_down",
            "Row Down",
            show=GLOBALS_HISTORY,
        ),

        Binding(
            kb_root("tree_screen"),
            "tree_screen",
            "Tree",
        ),
    ]

    def __init__(self, key: str) -> None:
        super().__init__()
        self._key = key
        self._vals: list[str] = []
        self._sel: int = 0
        self._syncing_input = False

    # ---------- UI ----------

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static(f"Global Editor - {self._key}", id="title")
            value_input = Input(placeholder="Enter value...", id="value-input")
            yield value_input

            yield SmartComplete(target=value_input, id="value-complete")
            with Vertical(id="history-container"):
                yield Static("", id="history-display")
            yield Footer()

    def on_mount(self) -> None:
        self.query_one("#value-input", Input).border_title = "Value"
        self.query_one("#history-display", Static).border_title = "History"

        from aliasr.core.globals import load_globals_raw

        raw = load_globals_raw()
        hist = raw.get(self._key, [])
        if not isinstance(hist, list):
            hist = [str(hist)] if hist else []

        self._vals = hist or [""]
        self._sel = 0

        self._render_history()
        self._sync_input()
        self.query_one("#value-input", Input).focus()

    def on_unmount(self) -> None:
        self._save_now()

    # ---------- Helpers ----------

    def _get_smart_complete(self) -> SmartComplete | None:
        """Get the SmartComplete widget."""
        try:
            return self.query_one("#value-complete", SmartComplete)
        except Exception:
            return None

    def _is_dropdown_visible(self) -> bool:
        """Check if SmartComplete dropdown is visible."""
        sc = self._get_smart_complete()
        return sc.is_dropdown_visible if sc else False

    def _clamp(self, n: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, n))

    def _select(self, idx: int) -> None:
        self._sel = self._clamp(idx, 0, len(self._vals) - 1)
        self._render_history()
        self._sync_input()

    def _render_history(self) -> None:
        disp = self.query_one("#history-display", Static)
        if not self._vals:
            disp.update("[dim]No history[/dim]")
            return

        N = 9
        start = max(0, self._sel - N // 2)
        end = min(len(self._vals), start + N)
        if end - start < N:
            start = max(0, end - N)

        lines = []
        if start > 0:
            lines.append("[dim]↑ more ...[/dim]")

        for i in range(start, end):
            v = self._vals[i]
            show = (
                "[dim](empty)[/dim]"
                if v == ""
                else (v[:50] + "..." if len(v) > 50 else v)
            )
            lines.append(
                f"[reverse] {i + 1}. {show} [/reverse]"
                if i == self._sel
                else f" {i + 1}. {show}"
            )

        if end < len(self._vals):
            lines.append("[dim]↓ more ...[/dim]")

        disp.update("\n".join(lines))

    def _sync_input(self) -> None:
        if not self._vals:
            return
        inp = self.query_one("#value-input", Input)
        self._syncing_input = True
        inp.value = self._vals[self._sel]
        self._syncing_input = False
        inp.action_select_all()

    def _swap(self, i: int, j: int) -> None:
        self._vals[i], self._vals[j] = self._vals[j], self._vals[i]

    def _save_now(self) -> str:
        from aliasr.core.globals import save_globals

        save_globals({self._key: list(self._vals)})
        if hasattr(self.app, "globals"):
            self.app.globals[self._key] = self._vals[0] or ""
        return self._vals[0] or ""

    # ---------- Actions ----------

    def action_cursor_up(self) -> None:
        # Route to SmartComplete if dropdown is visible
        if self._is_dropdown_visible():
            sc = self._get_smart_complete()
            if sc:
                sc.option_list.action_cursor_up()
        else:
            self._select(self._sel - 1)

    def action_cursor_down(self) -> None:
        # Route to SmartComplete if dropdown is visible
        if self._is_dropdown_visible():
            sc = self._get_smart_complete()
            if sc:
                sc.option_list.action_cursor_down()
        else:
            self._select(self._sel + 1)

    def action_page_up(self) -> None:
        # Route to SmartComplete if dropdown is visible
        if self._is_dropdown_visible():
            sc = self._get_smart_complete()
            if sc:
                sc.option_list.action_page_up()
        else:
            self._select(self._sel - 9)

    def action_page_down(self) -> None:
        # Route to SmartComplete if dropdown is visible
        if self._is_dropdown_visible():
            sc = self._get_smart_complete()
            if sc:
                sc.option_list.action_page_down()
        else:
            self._select(self._sel + 9)

    def action_delete_row(self) -> None:
        if not self._vals:
            return
        self._vals.pop(self._sel)
        if not self._vals:
            self._vals = [""]
            self._sel = 0
        else:
            self._select(min(self._sel, len(self._vals) - 1))
        self._save_now()

    def action_move_row_up(self) -> None:
        if len(self._vals) <= 1:
            return
        if self._sel == 0:
            self._swap(0, len(self._vals) - 1)
            self._select(len(self._vals) - 1)
        else:
            self._swap(self._sel, self._sel - 1)
            self._select(self._sel - 1)
        self._save_now()

    def action_move_row_down(self) -> None:
        if len(self._vals) <= 1:
            return
        last = len(self._vals) - 1
        if self._sel == last:
            self._swap(last, 0)
            self._select(0)
        else:
            self._swap(self._sel, self._sel + 1)
            self._select(self._sel + 1)
        self._save_now()

    def action_tree_screen(self) -> None:
        def _done(result: str | None) -> None:
            if result is None:
                return
            inp = self.query_one("#value-input", Input)
            inp.value = result
            inp.action_select_all()

        from aliasr.tui.tree_screen import TreeScreen

        self.app.push_screen(TreeScreen(), _done)

    def action_save(self) -> None:
        v = self._save_now()
        self.dismiss(v)

    def action_cancel(self) -> None:
        v = self._save_now()
        self.dismiss(v)

    # ---------- Events ----------

    @on(Input.Changed, "#value-input")
    def _changed(self, event: Input.Changed) -> None:
        if self._syncing_input or not self._vals:
            return
        self._vals[self._sel] = event.value
        self._render_history()

    @on(Input.Submitted, "#value-input")
    def _submitted(self, event: Input.Submitted) -> None:
        self._vals[self._sel] = event.value or ""
        self.action_save()
        event.stop()
