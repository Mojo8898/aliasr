from textual import on
from textual.containers import Horizontal
from textual.widgets import Input, Static

from aliasr.core.config import GLOBALS_HISTORY, CREDS_MASK


class Indicators(Horizontal):
    """Status/controls shown next to the main search input."""

    # ---------- UI ----------

    def compose(self):
        if self.app.in_tmux:
            yield Static("Pane:", id="tmux-label")
            pane = self.app.tmux_target_pane or self.app.tmux_current_pane or ""
            yield Input(value=str(pane), placeholder="..", id="tmux-input")
        else:
            yield Static(f"Tmux:  {self._badge(False)}  ", id="tmux-label")
        yield Static(f"History: {self._badge(GLOBALS_HISTORY)}", id="history-status")
        yield Static(f"Mask Creds: {self._badge(CREDS_MASK)}", id="mask-status")

    # ---------- Helpers ----------

    def _badge(self, ok: bool) -> str:
        theme = self.app.available_themes.get(self.app.theme)
        return f"[{theme.success}]✓[/]" if ok else f"[{theme.error}]✗[/]"

    # ---------- Events ----------

    @on(Input.Changed, "#tmux-input")
    def _tmux_changed(self, event: Input.Changed) -> None:
        v = (event.value or "").strip()
        self.app.tmux_target_pane = v if v.isdigit() else None
        if v:
            self.screen.query_one("#search", Input).focus()
