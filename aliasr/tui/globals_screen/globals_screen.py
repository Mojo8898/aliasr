from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.fuzzy import Matcher
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, OptionList, Static

from aliasr.core.config import kb_root, kb_table_copy
from aliasr.core.globals import (
    delete_globals,
    load_globals_raw,
    normalize_key,
    save_globals,
    save_globals_order,
)
from aliasr.tui.utils.tables import global_header, global_option, TABLE_BINDINGS


class GlobalsScreen(ModalScreen[bool | None]):
    """Globals manager screen."""

    BINDINGS = [
        Binding("escape", "cancel"),
        Binding(kb_root("globals_screen"), "cancel"),

        Binding("up", "list_up"),
        Binding("down", "list_down"),
        Binding("pageup", "list_page_up"),
        Binding("pagedown", "list_page_down"),

        *TABLE_BINDINGS,
        Binding(
            kb_table_copy("col_1"),
            "copy_global",
            "Global",
            tooltip="Copy the selected global key.",
        ),
        Binding(
            kb_table_copy("col_2"),
            "copy_value",
            "Value",
            tooltip="Copy the selected global value.",
        ),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._globals_cache: dict[str, str] = dict(getattr(self.app, "globals", {}))
        self._globals_order: list[str] = list(self._globals_cache.keys())
        self._original_order: list[str] = list(self._globals_order)
        self._olist: OptionList | None = None

    # ---------- UI ----------

    def compose(self) -> ComposeResult:
        with Vertical(id="panel", classes="menu-panel"):
            yield Static("Globals Menu", id="title")
            yield Input(placeholder="Search global to edit...", id="filter")
            yield Static(
                global_header(),
                id="globals-header",
                classes="optionlist-table-header",
            )
            yield OptionList(id="list", classes="optionlist-table")
            yield Footer()

    def on_mount(self) -> None:
        self._olist = self.query_one("#list", OptionList)
        self._olist.can_focus = False
        self._populate_option_list()
        self.query_one("#filter", Input).focus()

    # ---------- Internals ----------

    def _populate_option_list(self, query: str = "") -> None:
        if not self._olist:
            return
        self._olist.clear_options()

        if not query.strip():
            for key in self._globals_order:
                if key in self._globals_cache:
                    val = self._globals_cache.get(key, "")
                    self._olist.add_option(global_option(key, val))
        else:
            m = Matcher(query, case_sensitive=False)
            scored: list[tuple[int, str, str]] = []
            for key, val in self._globals_cache.items():
                s = m.match(f"{key} {val}")
                if s > 0:
                    scored.append((s, key, val))
            scored.sort(key=lambda t: t[0], reverse=True)
            for _, key, val in scored[:50]:
                self._olist.add_option(global_option(key, val))

        if self._olist.option_count:
            self._olist.highlighted = 0

    def _order_changed(self) -> bool:
        return self._original_order != self._globals_order

    def _sel_key(self) -> str | None:
        """Get the selected global key."""
        if self._olist and self._olist.highlighted is not None:
            opt = self._olist.get_option_at_index(self._olist.highlighted)
            return str(opt.id) if opt.id else None
        return None

    def _get_order_index(self, key: str) -> int | None:
        """Get the index of a key in the order list."""
        try:
            return self._globals_order.index(key)
        except ValueError:
            return None

    def _move_global(self, delta: int) -> None:
        """Move a global up or down in the order."""
        filter_input = self.query_one("#filter", Input)
        if filter_input.value.strip():
            return

        key = self._sel_key()
        if not key or len(self._globals_order) <= 1:
            return

        idx = self._get_order_index(key)
        if idx is None:
            return

        new_idx = (idx + delta) % len(self._globals_order)
        self._globals_order[idx], self._globals_order[new_idx] = (
            self._globals_order[new_idx],
            self._globals_order[idx],
        )

        self._sync_app_globals_order()
        save_globals_order(self._globals_order)

        self._populate_option_list(self.query_one("#filter", Input).value)

        for i in range(self._olist.option_count):
            opt = self._olist.get_option_at_index(i)
            if opt.id == key:
                self._olist.highlighted = i
                break

    def _open_editor(self, key: str) -> None:
        def _done(new_value: str | None) -> None:
            if new_value is None:
                return
            self._globals_cache[key] = new_value
            self._populate_option_list(self.query_one("#filter", Input).value)
            self._save_now()

        from aliasr.tui.globals_screen.global_editor import GlobalEditor
        self.app.push_screen(GlobalEditor(key), _done)

    def _save_now(self) -> None:
        self.app.globals.clear()
        for k in self._globals_order:
            if k in self._globals_cache:
                self.app.globals[k] = self._globals_cache[k]

        raw = load_globals_raw()
        payload: dict[str, list[str]] = {}

        for key in self._globals_order:
            if key not in self._globals_cache:
                continue
            v = self._globals_cache[key] or ""
            nk = normalize_key(key)
            if not nk:
                continue

            old = raw.get(nk, [])
            old_head = (
                old[0] if isinstance(old, list) and old else (str(old) if old else "")
            )
            if v == old_head:
                continue

            if v == "":
                payload[nk] = [""]
            else:
                old_list = old if isinstance(old, list) else ([str(old)] if old else [])
                seq = [v] + [x for x in old_list if str(x).strip() and x != v]
                payload[nk] = seq

        if payload:
            save_globals(payload)

    def _sync_app_globals_order(self) -> None:
        ordered: dict[str, str] = {}
        for k in self._globals_order:
            if k in self.app.globals:
                ordered[k] = self.app.globals[k]
        self.app.globals.clear()
        self.app.globals.update(ordered)

    def _copy_selected(self, field: str) -> None:
        """Copy the selected global's key or value to clipboard."""
        key = self._sel_key()
        if not key:
            return

        try:
            from aliasr.core.inject import copy_to_clipboard

            if field == "key":
                val = key
                label = "Global Name"
            else:
                val = self._globals_cache.get(key, "")
                label = "Global Value"

            if val:
                copy_to_clipboard(val)
                self.notify(f"Copied {label}!", severity="success", timeout=2.5)
        except Exception:
            self.notify("Copy Failed :(", severity="error", timeout=2.5)

    # ---------- Actions ----------

    def action_list_up(self) -> None:
        self._olist.action_cursor_up()

    def action_list_down(self) -> None:
        self._olist.action_cursor_down()

    def action_list_page_up(self) -> None:
        self._olist.action_page_up()

    def action_list_page_down(self) -> None:
        self._olist.action_page_down()

    def action_edit_row(self) -> None:
        key = self._sel_key()
        if key:
            self._open_editor(key)

    def action_add_row(self) -> None:
        def _done(result: tuple[str, str] | None) -> None:
            if not result:
                return
            key, val = result
            self._globals_cache[key] = val
            if key not in self._globals_order:
                self._globals_order.insert(0, key)
            self._populate_option_list(self.query_one("#filter", Input).value)
            self._save_now()

            # Select the new item
            for i in range(self._olist.option_count):
                opt = self._olist.get_option_at_index(i)
                if opt.id == key:
                    self._olist.highlighted = i
                    break

        from aliasr.tui.globals_screen.new_global import NewGlobal
        self.app.push_screen(NewGlobal(), _done)

    def action_delete_row(self) -> None:
        key = self._sel_key()
        if not key:
            return

        idx = self._get_order_index(key)
        if idx is None:
            return

        current_highlight = self._olist.highlighted
        next_key = None
        if idx + 1 < len(self._globals_order):
            next_key = self._globals_order[idx + 1]
        elif idx > 0:
            next_key = self._globals_order[idx - 1]

        self._globals_order.remove(key)
        self._globals_cache.pop(key, None)
        self.app.globals.pop(key, None)
        delete_globals([key])

        self._populate_option_list(self.query_one("#filter", Input).value)
        self._save_now()

        if next_key and self._olist.option_count > 0:
            found = False
            for i in range(self._olist.option_count):
                opt = self._olist.get_option_at_index(i)
                if opt.id == next_key:
                    self._olist.highlighted = i
                    found = True
                    break

            if not found:
                # Keep same position if possible
                self._olist.highlighted = min(
                    current_highlight, self._olist.option_count - 1
                )
        elif self._olist.option_count > 0:
            self._olist.highlighted = 0

    def action_move_row_up(self) -> None:
        self._move_global(-1)

    def action_move_row_down(self) -> None:
        self._move_global(1)

    def action_copy_global(self) -> None:
        """Copy the global's name/key."""
        self._copy_selected("key")

    def action_copy_value(self) -> None:
        """Copy the global's value."""
        self._copy_selected("value")

    def action_cancel(self) -> None:
        self.dismiss(self._order_changed())

    # ---------- Events ----------

    @on(Input.Changed, "#filter")
    def _on_filter(self, e: Input.Changed) -> None:
        self._populate_option_list(e.value)

    @on(Input.Submitted, "#filter")
    def _submit_filter(self, _: Input.Submitted) -> None:
        key = self._sel_key()
        if key:
            self._open_editor(key)

    @on(OptionList.OptionSelected, "#list")
    def _pick_from_list(self, e: OptionList.OptionSelected) -> None:
        if e.option.id:
            self._open_editor(str(e.option.id))
        e.stop()
