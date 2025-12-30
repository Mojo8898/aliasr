from math import ceil
from contextlib import contextmanager

from textual import on
from textual.binding import Binding
from textual.containers import Grid, Horizontal
from textual.widgets import Input

from aliasr.core.config import GLOBALS_ROWS, GLOBALS_COLUMNS, kb_root
from aliasr.tui.utils.grid_nav import GRID_NAV_BINDINGS, grid_nav
from aliasr.tui.utils.common import widget_id


CAP = GLOBALS_ROWS * GLOBALS_COLUMNS


class GlobalsGrid(Horizontal):
    """Responsive grid of editable globals with diff highlighting."""

    BINDINGS = [
        *GRID_NAV_BINDINGS,
        
        Binding(
            kb_root("globals_editor"),
            "open_editor",
            "Edit",
            priority=True,
            tooltip="Open the globals editor menu for the currently focused global.",
        ),
        Binding(
            kb_root("tree_screen"),
            "tree_screen",
            "Tree",
            tooltip="Open the tree menu for the currently focused global.",
        ),
        
        Binding(
            kb_root("cycle_grid_focus"),
            "focus_search",
            "Focus Search",
            priority=True
        ),
    ]

    def __init__(self, *children, **kwargs) -> None:
        super().__init__(*children, **kwargs)
        self._keys: list[str] = []
        self._saved: dict[str, str] = {}
        self._syncing = False

    # ---------- UI ----------

    def compose(self):
        self._refresh_saved_snapshot()
        data = self.app.globals
        self._keys = list(data.keys())[:CAP]

        with Grid(id="globals-grid"):
            for key in self._keys:
                wid = widget_id("g-", key)
                inp = Input(
                    value=data.get(key, ""), placeholder="Enter value...", id=wid
                )
                inp.border_title = key
                yield inp

    def on_mount(self) -> None:
        self._apply_layout()
        self._paint_all()

    # ---------- Helpers ----------

    @contextmanager
    def _no_sync(self):
        self._syncing = True
        try:
            yield
        finally:
            self._syncing = False

    def _apply_layout(self) -> None:
        grid = self.query_one("#globals-grid", Grid)
        n = len(self._keys)
        rows = max(1, ceil(n / GLOBALS_COLUMNS)) if n else 1
        grid.styles.grid_size_columns = GLOBALS_COLUMNS
        grid.styles.grid_size_rows = rows
        grid.refresh(layout=True)
        self.refresh(layout=True)

    def _refresh_saved_snapshot(self) -> None:
        self._saved = dict(getattr(self.app, "globals", {}))

    def _paint(self, key: str) -> None:
        wid = widget_id("g-", key)
        inp = self.query_one(f"#{wid}", Input)
        saved = self._saved.get(key, "")
        (
            inp.add_class("modified")
            if inp.value != saved
            else inp.remove_class("modified")
        )

    def _paint_all(self) -> None:
        for key in self._keys:
            try:
                self._paint(key)
            except Exception:
                pass

    def _focused_key(self) -> str | None:
        w = self.app.focused
        if isinstance(w, Input) and w.id and w.id.startswith("g-"):
            return w.id[2:]
        return None

    def _commit_value(self, key: str, value: str) -> None:
        if key not in self.app.globals:
            return
        self.app.globals[key] = value
        from aliasr.core.globals import save_global

        save_global(key, value)
        self._saved[key] = value
        try:
            self._paint(key)
        except Exception:
            pass

    # ---------- Actions ----------

    def action_grid_nav(self, direction: str) -> None:
        grid_nav(
            self,
            direction,
            grid_selector="#globals-grid",
            item_selector="Input",
            cols=GLOBALS_COLUMNS,
        )

    def action_open_editor(self) -> None:
        key = self._focused_key()
        if not key:
            return
        w = self.query_one(f"#{widget_id('g-', key)}", Input)
        cur = w.value or ""
        if (self._saved.get(key, "") or "") != cur:
            self._commit_value(key, cur)

        def _done(_: str | None) -> None:
            self.rebuild_from_store()
            w = self.query_one(f"#{widget_id('g-', key)}", Input)
            w.focus()
            w.action_select_all()

        from aliasr.tui.globals_screen.global_editor import GlobalEditor

        self.app.push_screen(GlobalEditor(key), _done)

    def action_tree_screen(self) -> None:
        key = self._focused_key()
        if not key:
            return

        def _done(path: str | None) -> None:
            if path is None:
                return
            self._commit_value(key, path)
            w = self.query_one(f"#{widget_id('g-', key)}", Input)
            w.focus()
            w.action_select_all()

        from aliasr.tui.tree_screen import TreeScreen

        self.app.push_screen(TreeScreen(), _done)

    def action_focus_search(self) -> None:
        """Switch focus to search input."""
        search = self.app.query_one("#search", Input)
        search.focus()
        search.action_select_all()

    # ---------- Events ----------

    @on(Input.Changed, "#globals-grid Input")
    def _changed(self, event: Input.Changed) -> None:
        if self._syncing:
            return
        w: Input = event.control
        if not (w.id and w.id.startswith("g-")):
            return
        key = w.id[2:]
        self._paint(key)

    @on(Input.Submitted, "#globals-grid Input")
    def _submitted(self, event: Input.Submitted) -> None:
        w: Input = event.control
        if not (w.id and w.id.startswith("g-")):
            return
        key = w.id[2:]
        self._commit_value(key, w.value)
        event.stop()
        self.app.query_one("#search", Input).focus()

    @on(Input.Blurred, "#globals-grid Input")
    def _blurred(self, event: Input.Blurred) -> None:
        w: Input = event.control
        if not (w.id and w.id.startswith("g-")):
            return
        key = w.id[2:]
        self._commit_value(key, w.value)

    # ---------- Public API ----------

    def commit_all_modified(self) -> None:
        """Persist any edited inputs so other screens (Globals menu/editor)
        see the latest values."""
        for key in list(self._keys):
            try:
                w = self.query_one(f"#{widget_id('g-', key)}", Input)
                cur = w.value or ""
            except Exception:
                cur = self.app.globals.get(key, "") or ""
            if (self._saved.get(key, "") or "") != cur:
                self._commit_value(key, cur)

    def rebuild_from_store(self) -> None:
        """Update grid to reflect current app.globals order/values."""
        grid = self.query_one("#globals-grid", Grid)
        data = self.app.globals
        new_keys = list(data.keys())[:CAP]

        desired_ids = {widget_id("g-", k) for k in new_keys}
        existing = {w.id: w for w in grid.query("Input")}

        # Remove stale inputs
        for wid, w in list(existing.items()):
            if wid not in desired_ids:
                w.remove()
                existing.pop(wid, None)

        # Add / update inputs
        for key in new_keys:
            wid = widget_id("g-", key)
            w = existing.get(wid)
            if w is None:
                w = Input(value=data.get(key, ""), placeholder="Enter value...", id=wid)
                w.border_title = key
                grid.mount(w)
                existing[wid] = w
            else:
                w.border_title = key
                new_val = data.get(key, "")
                if w.value != new_val:
                    with self._no_sync():
                        w.value = new_val

        self._keys = new_keys
        self._apply_layout()
        self._refresh_saved_snapshot()
        self._paint_all()
