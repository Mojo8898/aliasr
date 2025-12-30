from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.fuzzy import Matcher
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, OptionList, Static

from aliasr.core.config import kb_root, kb_table_copy
from aliasr.core.creds import Credential, load_creds, save_creds
from aliasr.tui.utils.tables import cred_header, cred_option, TABLE_BINDINGS


class CredsScreen(ModalScreen[None]):
    """Credentials management screen."""

    BINDINGS = [
        Binding("escape", "cancel"),
        Binding(kb_root("creds_screen"), "cancel"),
        
        Binding("up", "list_up"),
        Binding("down", "list_down"),
        Binding("pageup", "list_page_up"),
        Binding("pagedown", "list_page_down"),
        
        *TABLE_BINDINGS,
        Binding(
            kb_table_copy("col_1"),
            "copy_user",
            "User",
            tooltip="Copy the selected username.",
        ),
        Binding(
            kb_table_copy("col_2"),
            "copy_password",
            "Password",
            tooltip="Copy the selected password.",
        ),
        Binding(
            kb_table_copy("col_3"),
            "copy_hash",
            "Hash",
            tooltip="Copy the selected hash.",
        ),
        Binding(
            kb_table_copy("col_4"),
            "copy_domain",
            "Domain",
            tooltip="Copy the selected domain.",
        ),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._olist: OptionList | None = None
        self._rows: list[Credential] = []
        self._dirty: bool = False

    # ---------- UI ----------

    def compose(self) -> ComposeResult:
        with Vertical(id="panel", classes="menu-panel"):
            yield Static("Credentials Menu", id="title")
            yield Input(placeholder="Search credentials... (user/domain)", id="filter")
            yield Static(
                cred_header(),
                id="cred-header",
                classes="optionlist-table-header",
            )
            yield OptionList(id="list", classes="optionlist-table")
            yield Footer()

    def on_mount(self) -> None:
        self._olist = self.query_one("#list", OptionList)
        self._olist.can_focus = False

        try:
            loaded = load_creds()
            self._rows = list(loaded) if loaded else [Credential("", "", "", "")]
        except RuntimeError as e:
            self._rows = [Credential("Error", str(e), "", "")]
            self._olist.disabled = True

        self._populate_option_list()
        self.query_one("#filter", Input).focus()

    def on_unmount(self) -> None:
        if self._dirty:
            save_creds(self._non_empty_rows())
            self._dirty = False

    # ---------- Helpers ----------

    def _populate_option_list(self, query: str = "") -> None:
        if not self._olist:
            return
        self._olist.clear_options()

        if not query.strip():
            for i, c in enumerate(self._rows):
                self._olist.add_option(cred_option(c, i))
        else:
            m = Matcher(query, case_sensitive=False)
            scored = []
            for i, c in enumerate(self._rows):
                search_text = f"{c.username or ''} {c.domain or ''}"
                s = m.match(search_text)
                if s > 0:
                    scored.append((s, i, c))
            scored.sort(key=lambda t: t[0], reverse=True)
            for _, i, c in scored[:200]:
                self._olist.add_option(cred_option(c, i))

        if self._olist.option_count:
            self._olist.highlighted = 0

    def _non_empty_rows(self) -> list[Credential]:
        return [c for c in self._rows if not self._is_empty(c)]

    def _sel_row(self) -> int | None:
        if self._olist and self._olist.highlighted is not None:
            opt = self._olist.get_option_at_index(self._olist.highlighted)
            return opt.id if isinstance(opt.id, int) else None
        return None

    def _open_editor(self, row_idx: int) -> None:
        if not (0 <= row_idx < len(self._rows)):
            return

        c = self._rows[row_idx]

        def _done(res: tuple[str, str, str, str] | None) -> None:
            if res is None:
                return
            u, p, h, d = res
            self._rows[row_idx] = Credential(u, p, h, d)
            self._populate_option_list(self.query_one("#filter", Input).value)
            self._dirty = True

        from aliasr.tui.creds_screen.cred_editor import CredEditor

        self.app.push_screen(
            CredEditor(c.username, c.password, c.hash, c.domain), _done
        )

    def _is_empty(self, c: Credential) -> bool:
        return not any((c.username.strip(), c.password, c.hash, c.domain))

    def _move_row(self, delta: int) -> None:
        filter_input = self.query_one("#filter", Input)
        if filter_input.value.strip():
            return

        r = self._sel_row()
        if r is None or len(self._rows) <= 1 or not (0 <= r < len(self._rows)):
            return

        new_r = (r + delta) % len(self._rows)
        self._rows[r], self._rows[new_r] = self._rows[new_r], self._rows[r]

        # Refresh list
        self._populate_option_list(self.query_one("#filter", Input).value)

        # Find the new position in the filtered list
        for i in range(self._olist.option_count):
            opt = self._olist.get_option_at_index(i)
            if opt.id == new_r:
                self._olist.highlighted = i
                break

        self._dirty = True

    def _copy_selected(self, field: str) -> None:
        r = self._sel_row()
        if r is None or not (0 <= r < len(self._rows)):
            return
        try:
            from aliasr.core.inject import copy_to_clipboard

            val = getattr(self._rows[r], field, "") or ""
            if val:
                copy_to_clipboard(val)
                label = {
                    "username": "Username",
                    "password": "Password",
                    "hash": "NT Hash",
                    "domain": "Domain",
                }.get(field, field)
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

    def action_copy_user(self) -> None:
        self._copy_selected("username")

    def action_copy_password(self) -> None:
        self._copy_selected("password")

    def action_copy_hash(self) -> None:
        self._copy_selected("hash")

    def action_copy_domain(self) -> None:
        self._copy_selected("domain")

    def action_edit_row(self) -> None:
        r = self._sel_row()
        if r is not None:
            self._open_editor(r)

    def action_add_row(self) -> None:
        def _done(res: tuple[str, str, str, str] | None) -> None:
            if res is None:
                return
            u, p, h, d = res
            self._rows.insert(0, Credential(u, p, h, d))
            self._populate_option_list(self.query_one("#filter", Input).value)
            self._olist.highlighted = 0
            self._dirty = True

        from aliasr.tui.creds_screen.cred_editor import CredEditor

        self.app.push_screen(CredEditor("", "", "", ""), _done)

    def action_delete_row(self) -> None:
        r = self._sel_row()
        if r is None or not (0 <= r < len(self._rows)):
            return

        if len(self._rows) <= 1:
            self._rows = [Credential("", "", "", "")]
            self._populate_option_list(self.query_one("#filter", Input).value)
            self._dirty = True
            return

        # Remember the current highlight position and what item will be next
        current_highlight = self._olist.highlighted
        next_row_idx = r + 1 if r + 1 < len(self._rows) else r - 1 if r > 0 else None

        # Delete the row
        self._rows.pop(r)

        # Update indices for remaining rows (they shift after deletion)
        if next_row_idx is not None and next_row_idx > r:
            next_row_idx -= 1

        # Repopulate the list
        self._populate_option_list(self.query_one("#filter", Input).value)

        # Find where the "next" item ended up in the filtered list
        if next_row_idx is not None and self._olist.option_count > 0:
            # Try to find the item that was below (or above if we deleted the last item)
            found = False
            for i in range(self._olist.option_count):
                opt = self._olist.get_option_at_index(i)
                if opt.id == next_row_idx:
                    self._olist.highlighted = i
                    found = True
                    break

            # If the next item isn't in the filtered results, try to maintain position
            if not found:
                # Keep same position if possible, or go to end of list
                self._olist.highlighted = min(
                    current_highlight, self._olist.option_count - 1
                )
        elif self._olist.option_count > 0:
            self._olist.highlighted = 0

        self._dirty = True

    def action_move_row_up(self) -> None:
        self._move_row(-1)

    def action_move_row_down(self) -> None:
        self._move_row(1)

    def action_cancel(self) -> None:
        self.dismiss(None)

    # ---------- Events ----------

    @on(Input.Changed, "#filter")
    def _on_filter(self, e: Input.Changed) -> None:
        self._populate_option_list(e.value)

    @on(Input.Submitted, "#filter")
    def _submit_filter(self, _: Input.Submitted) -> None:
        if self._olist and self._olist.highlighted is not None:
            opt = self._olist.get_option_at_index(self._olist.highlighted)
            if isinstance(opt.id, int):
                self._open_editor(opt.id)

    @on(OptionList.OptionSelected, "#list")
    def _pick_from_list(self, e: OptionList.OptionSelected) -> None:
        if isinstance(e.option.id, int):
            self._open_editor(e.option.id)
        e.stop()
