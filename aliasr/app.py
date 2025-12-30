from importlib.resources import files
from pathlib import Path
from threading import Thread

from textual.app import App
from textual.binding import Binding
from textual.widgets import Input

from aliasr.core.config import kb_root, THEME
from aliasr.tui.main_screen.globals_grid import GlobalsGrid
from aliasr.tui.main_screen.main_screen import MainScreen
from aliasr.tui.theme import BUNDLED_THEMES


class Aliasr(App[None]):
    CSS_PATH = Path(files("aliasr") / "tui" / "main.tcss")

    BINDINGS = [
        Binding(
            "escape",
            "safe_exit",
        ),
        Binding(
            "ctrl+q",
            "safe_exit",
            priority=True,
        ),
        Binding(
            kb_root("quit"),
            "safe_exit",
            "Quit",
            priority=True,
        ),
        Binding(
            kb_root("copy_input"),
            "copy_input",
            "Copy",
            priority=True,
            tooltip="Copy the value of the currently focused input.",
        ),
    ]

    def __init__(
        self,
        *,
        in_tmux: bool = False,
        execute_cmd: bool = False,
        tmux_current_pane: str | None = None,
        tmux_target_pane: str | None = None,
    ) -> None:
        super().__init__()
        self.animation_level = "none"
        self.pending_inject: str | None = None
        self.in_tmux = in_tmux
        self.execute_cmd = execute_cmd
        self.tmux_current_pane = tmux_current_pane
        self.tmux_target_pane = tmux_target_pane
        self.globals: dict[str, str] = {}
        self.cheats: list = []

    # ---------- UI ----------

    def on_mount(self) -> None:
        theme = BUNDLED_THEMES.get(THEME.name)
        if theme:
            self.register_theme(theme)
        try:
            self.theme = THEME.name
        except Exception:
            self.register_theme(BUNDLED_THEMES["aliasr"])
            self.theme = "aliasr"

        def _background_load():
            from aliasr.core.creds import load_creds
            from aliasr.core.variations import load_variations

            load_creds()
            load_variations()

        Thread(target=_background_load, daemon=True).start()

    # ---------- Actions ----------

    def action_copy_input(self) -> None:
        w = self.focused
        if isinstance(w, Input):
            from aliasr.core.inject import copy_to_clipboard

            if w.value:
                copy_to_clipboard(w.value or "")
                self.notify("Copied Input Value!", severity="success", timeout=2.5)

    def action_safe_exit(self) -> None:
        for grid in self.query(GlobalsGrid):
            grid.commit_all_modified()
        self.exit()

    # ---------- Public API ----------

    def get_default_screen(self) -> MainScreen:
        return MainScreen()
