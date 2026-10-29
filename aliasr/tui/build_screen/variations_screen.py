from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.fuzzy import Matcher
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static, TabbedContent, TabPane, Tabs
from textual.widgets.option_list import Option

from aliasr.core.config import kb_build_screen, kb_root
from aliasr.core.variations import Variation


class VariationsScreen(ModalScreen[dict[str, str] | None]):
    BINDINGS = [
        Binding("escape", "cancel"),
        Binding(kb_build_screen("variations_screen"), "cancel"),
        Binding("up", "list_up"),
        Binding("down", "list_down"),
        Binding("pageup", "list_page_up"),
        Binding("pagedown", "list_page_down"),
        Binding(kb_root("prev_tab"), "prev_tab"),
        Binding(kb_root("next_tab"), "next_tab"),
        Binding("ctrl+up", "preview_up", show=False),
        Binding("ctrl+down", "preview_down", show=False),
        Binding("ctrl+pageup", "preview_page_up", show=False),
        Binding("ctrl+pagedown", "preview_page_down", show=False),
    ]

    def __init__(
        self,
        cmd: str,
        all_variations: dict[str, list[Variation]],
    ) -> None:
        super().__init__()
        self._cmd = cmd
        self._vars = all_variations
        self._sel: dict[str, str] = {}
        self._preview_values: dict[
            str, str
        ] = {}  # Track highlighted values for preview
        self._lists: dict[str, OptionList] = {}
        self._filters: dict[str, Input] = {}
        self._params = list(self._vars.keys())
        self._preview: Static | None = None

    # ---------- UI ----------

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            with VerticalScroll(id="preview-scroll"):
                self._preview = Static(self._cmd, id="preview")
                yield self._preview
            with TabbedContent(id="tc"):
                for p in self._params:
                    with TabPane(p, id=p):
                        yield Input(
                            placeholder=f"Search {p} variations...", id=f"{p}-filter"
                        )
                        yield OptionList(id=f"{p}-list", classes="build-optionlist")

    def on_mount(self) -> None:
        # Preview scrolls on its own scrollbar; keep it out of the Tab cycle.
        self.query_one("#preview-scroll").can_focus = False
        if not self._vars:
            self.dismiss(None)
            return

        tc = self._tc()
        tc.query_one(Tabs).can_focus = False

        for p in self._params:
            lst = self.query_one(f"#{p}-list", OptionList)
            lst.can_focus = False
            flt = self.query_one(f"#{p}-filter", Input)
            self._lists[p] = lst
            self._filters[p] = flt

            for v in self._vars[p]:
                lst.add_option(Option(v.key, id=v.value))

            if lst.option_count:
                lst.highlighted = 0
                # Initialize preview value for this parameter
                self._preview_values[p] = lst.get_option_at_index(0).id or ""

        # ensure a valid active pane and focus its filter
        if tc.active not in self._params and self._params:
            tc.active = self._params[0]
        self._filters[self._active_param()].focus()

        # Initial preview update
        self._update_preview()

    # ---------- Internals ----------

    def _tc(self) -> TabbedContent:
        return self.query_one("#tc", TabbedContent)

    def _tabs(self) -> Tabs | None:
        q = self._tc().query(Tabs)
        return q.first(Tabs) if q else None

    def _active_param(self) -> str:
        return self._tc().active

    def _active_list(self) -> OptionList | None:
        return self._lists.get(self._active_param())

    def _update_preview(self) -> None:
        """Preview the command with the highlighted variation keys expanded.

        Each line is resolved against its own command head, so a single pick
        renders with that command's own syntax (e.g. ``-k`` vs ``--use-kcache``)
        across the different commands of a multi-line cheat.
        """
        if not self._preview:
            return

        import re

        from aliasr.core.variations import command_head, lookup_value

        theme = self.app.current_theme
        placeholder_re = re.compile(r"<([^>\s]+)>")
        text = Text()

        for li, line in enumerate(self._cmd.split("\n")):
            if li:
                text.append("\n")
            head = command_head(line)
            pos = 0
            for match in placeholder_re.finditer(line):
                if match.start() > pos:
                    text.append(line[pos : match.start()])
                param_name = match.group(1).split("|", 1)[0]
                key = self._preview_values.get(param_name)
                value = lookup_value(head, param_name, key) if key else None
                if value is not None:
                    text.append(value, style=theme.primary)
                else:
                    text.append(match.group(0))  # unresolved here -> keep placeholder
                pos = match.end()
            if pos < len(line):
                text.append(line[pos:])

        self._preview.update(text)

    def _store_active_selection(self) -> None:
        lst = self._active_list()
        if not lst or lst.option_count == 0:
            return
        idx = lst.highlighted if lst.highlighted is not None else 0
        self._sel[self._active_param()] = lst.get_option_at_index(idx).id or ""

    def _filter_param(self, param: str, query: str) -> None:
        lst = self._lists[param]
        items = self._vars[param]
        lst.clear_options()
        if not query.strip():
            for v in items:
                lst.add_option(Option(v.key, id=v.value))
        else:
            m = Matcher(query, case_sensitive=False)
            scored = []
            for v in items:
                s = max(m.match(v.key), m.match(v.value))
                if s > 0:
                    scored.append((s, v))
            scored.sort(key=lambda x: x[0], reverse=True)
            for _, v in scored[:50]:
                disp = m.highlight(v.key) if m.match(v.key) > 0 else v.key
                lst.add_option(Option(disp, id=v.value))
        if lst.option_count:
            lst.highlighted = 0
            # Update preview value for this parameter
            self._preview_values[param] = lst.get_option_at_index(0).id or ""
            self._update_preview()

    def _on_highlight_changed(self, param: str) -> None:
        """Called when the highlighted option changes for a parameter."""
        lst = self._lists[param]
        if lst.highlighted is not None and lst.option_count > 0:
            self._preview_values[param] = (
                lst.get_option_at_index(lst.highlighted).id or ""
            )
            self._update_preview()

    # ---------- Actions ----------

    def action_prev_tab(self) -> None:
        t = self._tabs()
        if t:
            t.action_previous_tab()

    def action_next_tab(self) -> None:
        t = self._tabs()
        if t:
            t.action_next_tab()

    def action_list_up(self) -> None:
        lst = self._active_list()
        if lst:
            old_highlight = lst.highlighted
            lst.action_cursor_up()
            if lst.highlighted != old_highlight:
                self._on_highlight_changed(self._active_param())

    def action_list_down(self) -> None:
        lst = self._active_list()
        if lst:
            old_highlight = lst.highlighted
            lst.action_cursor_down()
            if lst.highlighted != old_highlight:
                self._on_highlight_changed(self._active_param())

    def action_list_page_up(self) -> None:
        lst = self._active_list()
        if lst:
            old_highlight = lst.highlighted
            lst.action_page_up()
            if lst.highlighted != old_highlight:
                self._on_highlight_changed(self._active_param())

    def action_list_page_down(self) -> None:
        lst = self._active_list()
        if lst:
            old_highlight = lst.highlighted
            lst.action_page_down()
            if lst.highlighted != old_highlight:
                self._on_highlight_changed(self._active_param())

    def action_submit(self) -> None:
        self._store_active_selection()
        # ensure single-param selection if user never moved cursor
        if len(self._params) == 1 and self._params[0] not in self._sel:
            lst = self._active_list()
            if lst and lst.option_count:
                self._sel[self._params[0]] = (
                    lst.get_option_at_index(lst.highlighted or 0).id or ""
                )
        self.dismiss(self._sel)

    def action_cancel(self) -> None:
        self.dismiss(None)

    # ---------- Preview scrolling ----------

    def _scroll_preview(self, method: str) -> None:
        try:
            ps = self.query_one("#preview-scroll")
        except Exception:
            return
        getattr(ps, method)(animate=False)

    def action_preview_up(self) -> None:
        self._scroll_preview("scroll_up")

    def action_preview_down(self) -> None:
        self._scroll_preview("scroll_down")

    def action_preview_page_up(self) -> None:
        self._scroll_preview("scroll_page_up")

    def action_preview_page_down(self) -> None:
        self._scroll_preview("scroll_page_down")

    # ---------- Events ----------

    @on(TabbedContent.TabActivated, "#tc")
    def _tab_activated(self, _: TabbedContent.TabActivated) -> None:
        f = self._filters.get(self._active_param())
        if f:
            f.focus()

    @on(Input.Changed)
    def _on_filter_changed(self, e: Input.Changed) -> None:
        for p in self._params:
            if e.control.id == f"{p}-filter":
                self._filter_param(p, e.value)
                return

    @on(OptionList.OptionHighlighted)
    def _on_option_highlighted(self, e: OptionList.OptionHighlighted) -> None:
        """Update preview when an option is highlighted."""
        for p in self._params:
            if e.control.id == f"{p}-list":
                self._preview_values[p] = e.option.id or ""
                self._update_preview()
                return

    @on(OptionList.OptionSelected)
    def _pick(self, e: OptionList.OptionSelected) -> None:
        self._sel[self._active_param()] = e.option.id or ""
        if len(self._params) > 1:
            for p in self._params:
                if p not in self._sel:
                    self._tc().active = p
                    return
        self.dismiss(self._sel)
        e.stop()

    @on(Input.Submitted)
    def _submit_from_filter(self, e: Input.Submitted) -> None:
        self._store_active_selection()
        if len(self._params) > 1:
            for p in self._params:
                if p not in self._sel:
                    self._tc().active = p
                    return
        self.action_submit()
        e.stop()
