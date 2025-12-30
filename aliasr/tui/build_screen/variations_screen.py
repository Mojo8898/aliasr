from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.fuzzy import Matcher
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static, TabbedContent, TabPane, Tabs
from textual.widgets.option_list import Option

from aliasr.core.config import kb_build_screen, kb_root
from aliasr.core.variations import Variation, apply_variation


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
        self._preview_values: dict[str, str] = {}  # Track highlighted values for preview
        self._lists: dict[str, OptionList] = {}
        self._filters: dict[str, Input] = {}
        self._params = list(self._vars.keys())
        self._preview: Static | None = None

    # ---------- UI ----------

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
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
        if not self._vars:
            self.dismiss(None)
            return

        # hide tab strip if only one pane
        tc = self._tc()
        tc.query_one(Tabs).can_focus = False
        tc.show_tabs = len(self._params) > 1

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
                self._preview_values[p] = lst.get_option_at_index(0).id

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
        """Update the preview with currently highlighted variations."""
        if not self._preview:
            return
        
        # Build the preview text
        preview_cmd = self._cmd
        for param, value in self._preview_values.items():
            if value:
                preview_cmd = apply_variation(preview_cmd, param, value)
        
        # Style the preview
        theme = self.app.available_themes.get(self.app.theme)
        
        # Create a Text object with styled substituted values
        import re
        text = Text()
        placeholder_re = re.compile(r"<([^>\s]+)>")
        
        pos = 0
        for match in placeholder_re.finditer(self._cmd):
            # Add literal text before the placeholder
            if match.start() > pos:
                text.append(self._cmd[pos:match.start()])
            
            # Get the parameter name from the placeholder
            token = match.group(1)
            param_name = token.split("|", 1)[0]
            
            # Add the substituted value with styling
            if param_name in self._preview_values:
                value = self._preview_values[param_name]
                text.append(value, style=theme.primary)
            else:
                # Keep the original placeholder if no variation selected
                text.append(match.group(0))
            
            pos = match.end()
        
        # Add any remaining literal text
        if pos < len(self._cmd):
            text.append(self._cmd[pos:])
        
        self._preview.update(text)

    def _store_active_selection(self) -> None:
        lst = self._active_list()
        if not lst or lst.option_count == 0:
            return
        idx = lst.highlighted if lst.highlighted is not None else 0
        self._sel[self._active_param()] = lst.get_option_at_index(idx).id

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
            self._preview_values[param] = lst.get_option_at_index(0).id
            self._update_preview()

    def _on_highlight_changed(self, param: str) -> None:
        """Called when the highlighted option changes for a parameter."""
        lst = self._lists[param]
        if lst.highlighted is not None and lst.option_count > 0:
            self._preview_values[param] = lst.get_option_at_index(lst.highlighted).id
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
                self._sel[self._params[0]] = lst.get_option_at_index(
                    lst.highlighted or 0
                ).id
        self.dismiss(self._sel)

    def action_cancel(self) -> None:
        self.dismiss(None)

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
                self._preview_values[p] = e.option.id
                self._update_preview()
                return

    @on(OptionList.OptionSelected)
    def _pick(self, e: OptionList.OptionSelected) -> None:
        self._sel[self._active_param()] = e.option.id
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
