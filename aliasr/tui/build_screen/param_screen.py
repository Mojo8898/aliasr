from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.fuzzy import Matcher
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static, TabbedContent, TabPane, Tabs
from textual.widgets.option_list import Option

from aliasr.core.config import kb_root, kb_build_screen
from aliasr.tui.utils.tables import cred_header, cred_option


class ParamScreen(ModalScreen[str | dict[str, str] | None]):
    """Parameter selection screen using TabbedContent."""

    BINDINGS = [
        Binding("escape", "cancel"),
        Binding(kb_build_screen("param_screen"), "cancel"),

        Binding("up", "list_up"),
        Binding("down", "list_down"),
        Binding("pageup", "list_page_up"),
        Binding("pagedown", "list_page_down"),

        Binding(kb_root("prev_tab"), "prev_tab"),
        Binding(kb_root("next_tab"), "next_tab"),
    ]

    def __init__(self, param: str, options: list[str], history: list[str]) -> None:
        super().__init__()
        self._param = param
        self._show_creds = param in {"user", "password", "nt_hash", "domain"}
        self._refs = options or []
        self._history = history or []
        self._creds = None
        self._creds_loaded = False

    # ---------- UI ----------

    def compose(self) -> ComposeResult:
        have_refs = bool(self._refs)
        have_hist = bool(self._history)
        have_creds = self._show_creds  # actual list is lazy

        with Vertical(id="panel", classes="menu-panel"):
            yield Static(f"Select value for <{self._param}>", id="title")
            with TabbedContent(id="tc"):
                if have_refs:
                    with TabPane("References", id="references"):
                        yield Input(
                            placeholder="Search references...", id="reference-filter"
                        )
                        yield OptionList(
                            id="reference-list", classes="build-optionlist"
                        )
                if have_hist:
                    with TabPane("History", id="history"):
                        yield Input(
                            placeholder="Search history...", id="history-filter"
                        )
                        yield OptionList(id="history-list", classes="build-optionlist")
                if have_creds:
                    with TabPane("Credentials", id="credentials"):
                        yield Input(
                            placeholder="Search credentials... (user/domain)",
                            id="credential-filter",
                        )
                        yield Static(
                            cred_header(),
                            id="credential-header",
                            classes="optionlist-table-header",
                        )
                        yield OptionList(
                            id="credential-list",
                            classes="optionlist-table",
                        )

    def on_mount(self) -> None:
        self._tc().can_focus = False
        self._load_creds_if_needed()
        if (
            not self._refs
            and not self._history
            and not (self._show_creds and self._creds)
        ):
            self.dismiss(None)
            return

        self.query_one(OptionList).can_focus = False
        if self._refs:
            self._populate_simple_list("#reference-list", self._refs)
        if self._history:
            self._populate_simple_list("#history-list", self._history)

    # ---------- Internals ----------

    def _tc(self) -> TabbedContent:
        return self.query_one("#tc", TabbedContent)

    def _active_pane_id(self) -> str | None:
        return self._tc().active

    def _tabs(self) -> Tabs | None:
        tc = self._tc()
        q = tc.query(Tabs)
        return q.first(Tabs) if q else None

    def _active_list(self) -> OptionList | None:
        pid = self._active_pane_id()
        if pid == "references":
            return self.query_one("#reference-list", OptionList)
        if pid == "history":
            return self.query_one("#history-list", OptionList)
        if pid == "credentials":
            return self.query_one("#credential-list", OptionList)
        return None

    def _focus_active_filter(self) -> None:
        pid = self._active_pane_id()
        if pid == "references":
            self.query_one("#reference-filter", Input).focus()
        elif pid == "history":
            self.query_one("#history-filter", Input).focus()
        elif pid == "credentials":
            self.query_one("#credential-filter", Input).focus()

    def _populate_simple_list(self, selector: str, items: list[str]) -> None:
        lst = self.query_one(selector, OptionList)
        lst.clear_options()
        lst.add_options([Option(v, id=v) for v in items])
        if lst.option_count:
            lst.highlighted = 0

    def _load_creds_if_needed(self) -> None:
        if self._creds_loaded or not self._show_creds:
            return
        self._creds_loaded = True
        try:
            from aliasr.core.creds import load_creds

            self._creds = load_creds()
        except Exception:
            self._creds = []

    def _populate_creds(self, query: str = "") -> None:
        if not self._show_creds:
            return
        self._load_creds_if_needed()
        lst = self.query_one("#credential-list", OptionList)
        lst.clear_options()
        if not self._creds:
            return
        if not query.strip():
            lst.add_options([cred_option(c, i) for i, c in enumerate(self._creds)])
        else:
            m = Matcher(query, case_sensitive=False)
            scored = []
            for i, c in enumerate(self._creds):
                key = f"{c.username or ''} {c.domain or ''}".strip()
                s = m.match(key)
                if s > 0:
                    scored.append((s, i, c))
            scored.sort(key=lambda t: t[0], reverse=True)
            lst.add_options([cred_option(c, i) for _, i, c in scored[:200]])
        if lst.option_count:
            lst.highlighted = 0

    # ---------- Actions ----------

    def action_list_up(self) -> None:
        lst = self._active_list()
        if lst:
            lst.action_cursor_up()

    def action_list_down(self) -> None:
        lst = self._active_list()
        if lst:
            lst.action_cursor_down()

    def action_list_page_up(self) -> None:
        lst = self._active_list()
        if lst:
            lst.action_page_up()

    def action_list_page_down(self) -> None:
        lst = self._active_list()
        if lst:
            lst.action_page_down()

    def action_submit(self) -> None:
        lst = self._active_list()
        if not lst:
            self.dismiss(None)
            return
        idx = (
            lst.highlighted
            if lst.highlighted is not None
            else (0 if lst.option_count else None)
        )
        if idx is None:
            self.dismiss(None)
            return
        opt = lst.get_option_at_index(idx)

        if self._active_pane_id() == "credentials":
            i = opt.id if isinstance(opt.id, int) else None
            cred = (
                self._creds[i]
                if (i is not None and 0 <= i < len(self._creds or []))
                else None
            )
            self._dismiss_for_cred(cred)
        else:
            self.dismiss(opt.id or str(opt.prompt))

    def _dismiss_for_cred(self, cred) -> None:
        if cred is None:
            self.dismiss(None)
            return
        payload = {
            "user": cred.username or "",
            "password": cred.password or "",
            "nt_hash": cred.hash or "",
            "domain": cred.domain or "",
        }
        self.dismiss(payload)

    def action_cancel(self) -> None:
        self.dismiss(None)

    # ---------- Events ----------

    @on(TabbedContent.TabActivated, "#tc")
    def _tab_activated(self, _: TabbedContent.TabActivated) -> None:
        if self._active_pane_id() == "credentials":
            self._populate_creds()
        self._focus_active_filter()

    def action_prev_tab(self) -> None:
        t = self._tabs()
        if t:
            t.action_previous_tab()

    def action_next_tab(self) -> None:
        t = self._tabs()
        if t:
            t.action_next_tab()

    @on(Input.Changed, "#reference-filter")
    def _reference_filter(self, event: Input.Changed) -> None:
        if not self._refs:
            return
        q = event.value or ""
        if not q:
            self._populate_simple_list("#reference-list", self._refs)
            return
        m = Matcher(q, case_sensitive=False)
        scored = [(m.match(v), v) for v in self._refs]
        scored = [(s, v) for s, v in scored if s > 0]
        scored.sort(key=lambda t: t[0], reverse=True)
        lst = self.query_one("#reference-list", OptionList)
        lst.clear_options()
        lst.add_options([Option(m.highlight(v), id=v) for _, v in scored[:200]])
        if lst.option_count:
            lst.highlighted = 0

    @on(Input.Submitted, "#reference-filter")
    def _submit_from_reference_filter(self, _: Input.Submitted) -> None:
        self.action_submit()

    @on(OptionList.OptionSelected, "#reference-list")
    def _pick_from_refs(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id or str(event.option.prompt))

    @on(Input.Changed, "#history-filter")
    def _hist_filter(self, event: Input.Changed) -> None:
        if not self._history:
            return
        q = event.value or ""
        if not q:
            self._populate_simple_list("#history-list", self._history)
            return
        m = Matcher(q, case_sensitive=False)
        scored = [(m.match(v), v) for v in self._history]
        scored = [(s, v) for s, v in scored if s > 0]
        scored.sort(key=lambda t: t[0], reverse=True)
        lst = self.query_one("#history-list", OptionList)
        lst.clear_options()
        lst.add_options([Option(m.highlight(v), id=v) for _, v in scored[:200]])
        if lst.option_count:
            lst.highlighted = 0

    @on(Input.Submitted, "#history-filter")
    def _submit_from_hist_filter(self, _: Input.Submitted) -> None:
        self.action_submit()

    @on(OptionList.OptionSelected, "#history-list")
    def _pick_from_hist(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id or str(event.option.prompt))

    @on(Input.Changed, "#credential-filter")
    def _credential_filter(self, event: Input.Changed) -> None:
        self._populate_creds(event.value or "")

    @on(Input.Submitted, "#credential-filter")
    def _submit_from_credential_filter(self, _: Input.Submitted) -> None:
        self.action_submit()

    @on(OptionList.OptionSelected, "#credential-list")
    def _pick_from_creds(self, event: OptionList.OptionSelected) -> None:
        idx = event.option.id if isinstance(event.option.id, int) else None
        cred = (
            self._creds[idx]
            if (idx is not None and 0 <= idx < len(self._creds or []))
            else None
        )
        self._dismiss_for_cred(cred)
