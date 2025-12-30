from pathlib import Path
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.events import Click, MouseScrollUp, MouseScrollDown, Resize
from textual.fuzzy import FuzzySearch
from textual.screen import Screen
from textual.widgets import Footer, Input, Select, Tabs

from aliasr.core.config import GLOBALS_SHOW_GRID, kb_root
from aliasr.core.cheats import build_tag_index
from aliasr.tui.main_screen.cheatlist import CheatCommandList, CheatTitleList
from aliasr.tui.main_screen.globals_grid import GlobalsGrid
from aliasr.tui.main_screen.header import CheatHeader
from aliasr.tui.main_screen.search_bar.search_bar import MainSearch
from aliasr.tui.utils.common import widget_id
from aliasr.tui.utils.smart_complete import SmartComplete

class MainScreen(Screen[None]):
    BINDINGS = [
        Binding("up", "select_previous",),
        Binding("down", "select_next"),
        Binding("pageup", "page_up"),
        Binding("pagedown", "page_down"),

        Binding(
            kb_root("globals_screen"),
            "globals_screen",
            "Globals",
            tooltip="Open the globals menu.",
        ),
        Binding(
            kb_root("creds_screen"),
            "creds_screen",
            "Creds",
            tooltip="Open the credentials menu.",
        ),

        Binding(
            kb_root("cycle_grid_focus"),
            "cycle_grid_focus",
            "Grid",
            tooltip="Switch focus to the globals grid.",
        ),
        Binding(
            kb_root("cycle_filter_focus"),
            "cycle_filter_focus",
            "Filter",
            tooltip="Switch focus between search and filter inputs.",
        ),
        Binding(
            kb_root("cycle_select_focus"),
            "cycle_select_focus", 
            "Selects",
            tooltip="Switch focus between search and select dropdowns.",
        ),

        Binding(
            kb_root("toggle_grid"),
            "toggle_grid",
            "Toggle Grid",
            tooltip="Toggle the visibility of the globals grid."
        ),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._fz: FuzzySearch | None = FuzzySearch(cache_size=1024)
        self._keys: dict[int, str] = {}
        self._search: Input | None = None
        self.tag_to_cheats: dict[str, list] = {}
        self.current_tag: str = ""
        self.matches: list = []
        self.selected_idx: int = 0

    # ---------- UI ----------

    def compose(self) -> ComposeResult:
        yield Vertical(
            CheatHeader(id="header"),
            MainSearch(id="search-bar"),
            Horizontal(
                CheatTitleList(id="title-list"),
                CheatCommandList(id="command-list"),
                id="cheat-list",
            ),
            GlobalsGrid(id="globals"),
            Footer(),
            id="root",
        )

    def on_mount(self) -> None:
        for t in self.query(Tabs):
            t.can_focus = False
        self.header = self.query_one("#header", CheatHeader)
        self.title_list = self.query_one("#title-list", CheatTitleList)
        self.command_list = self.query_one("#command-list", CheatCommandList)
        self.globals_panel = self.query_one(GlobalsGrid)
        self.globals_panel.display = GLOBALS_SHOW_GRID
        self.matches = list(getattr(self.app, "cheats", []))
        for c in getattr(self.app, "cheats", []):
            first = (c.cmd.splitlines()[0] if c.cmd else "")[:200]
            self._keys[id(c)] = f"{c.title} {first}".lower()
        self._sync_lists()
        self.call_after_refresh(self._update_header)

        self.tag_to_cheats, tags = build_tag_index()

        # Pass ALL tags to the tabs widget (don't filter here!)
        self.current_tag = "all"
        sb = self.query_one("#search-bar", MainSearch)
        sb.query_one("#tabs").set_tags(tags, self.current_tag)  # Pass ALL tags
        sb.build_dynamic_tag_types()

        # Apply initial filters to show appropriate tabs
        sb._apply_filters()

        self.refresh_matches()

        # Add initial size check after layout is complete
        def _check_initial_size():
            if self.title_list.size.height <= 1:
                if self.globals_panel.display:
                    self._focus_search_if_focused_globals()
                    self.globals_panel.display = False

        self.call_after_refresh(_check_initial_size)

    # ---------- Helpers ----------

    def _search_cheats(self, items, query: str):
        q = (query or "").strip().lower()
        if not q:
            # Cap matches to 100
            return items[:100]

        toks = q.split()
        scored: list[tuple[float, object]] = []

        for c in items:
            key = self._keys.get(id(c))
            if not key:
                first = (c.cmd.splitlines()[0] if c.cmd else "")[:200]
                key = f"{c.title} {first}".lower()
                self._keys[id(c)] = key

            if any(t not in key for t in toks):
                continue

            s_all, _ = self._fz.match(q, key)
            if s_all <= 0:
                continue
            s_title, _ = self._fz.match(q, c.title or "")
            score = s_all + 0.15 * s_title
            scored.append((score, c))

        if not scored:
            return []

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:100]]

    def _set_selected(self, idx: int) -> None:
        if not self.matches:
            return
        idx = self._clamp(idx, 0, len(self.matches) - 1)
        self.selected_idx = idx
        self.title_list.set_selected(idx)
        self.command_list.set_selected(idx)
        self._update_header()

    def _page(self, direction: int) -> None:
        if not self.matches:
            return
        rows = self.title_list.visible_rows()
        top = self.title_list.top
        last = len(self.matches) - 1
        max_top = max(0, len(self.matches) - rows)
        bottom = min(top + rows - 1, last)

        if direction > 0:
            if self.selected_idx < bottom:
                self._set_selected(bottom)
                return
            new_top = self._clamp(top + rows, 0, max_top)
            select_idx = min(new_top + rows - 1, last)
        else:
            if self.selected_idx > top:
                self._set_selected(top)
                return
            new_top = self._clamp(top - rows, 0, max_top)
            select_idx = new_top

        self.title_list.page_to(new_top, place="top")
        self.command_list.page_to(new_top, place="top")
        self._set_selected(select_idx)

    def _select_all(self, w: Input) -> None:
        try:
            w.action_select_all()
        except Exception:
            w.selection_start = 0
            w.selection_end = len(w.value or "")

    def _sync_lists(self) -> None:
        self.title_list.set_list(self.matches, self.selected_idx)
        self.command_list.set_list(self.matches, self.selected_idx)

    def _clamp(self, n: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, n))

    def _remount_globals_grid(self, keep_visible: bool) -> None:
        root = self.query_one("#root", Vertical)
        old = root.query_one(GlobalsGrid)
        footer = self.query("Footer").first()

        async def _replace():
            if old:
                await old.remove()
            new = GlobalsGrid(id="globals")
            if footer:
                await root.mount(new, before=footer)
            else:
                await root.mount(new)
            self.globals_panel = new
            self.globals_panel.display = keep_visible and self.title_list.size.height > 1

        self.call_next(_replace)

    def _refocus_after_globals(self, prev_key: str | None) -> None:
        def _do():
            try:
                if prev_key and prev_key in self.app.globals:
                    w = self.query_one(f"#{widget_id('g-', prev_key)}", Input)
                    w.focus()
                    self._select_all(w)
                    return
            except Exception:
                pass
            s = self.query_one("#search", Input)
            s.focus()
            self._select_all(s)

        self.call_after_refresh(_do)

    def _first_globals_input(self) -> Input | None:
        grid = self.query_one(GlobalsGrid)
        return next(iter(grid.query("#globals-grid Input")), None)

    def _update_header(self) -> None:
        if self.matches:
            c = self.matches[self.selected_idx]
            self.header.set_current(c.title, c.cmd)
        else:
            self.header.set_current("", "")

    def _focus_search_if_focused_globals(self) -> None:
        in_globals = isinstance(self.focused, Input) and str(
            getattr(self.focused, "id", "")
        ).startswith("g-")
        if not in_globals:
            return
        s = self.query_one("#search", Input)
        self.call_after_refresh(lambda: (s.focus(), self._select_all(s)))

    def _focused_global_key(self) -> str | None:
        w = self.focused
        wid = getattr(w, "id", "") if isinstance(w, Input) else ""
        return wid[2:] if wid.startswith("g-") else None

    # ---------- Actions ----------

    def action_select_previous(self) -> None:
        self._set_selected(self.selected_idx - 1)

    def action_select_next(self) -> None:
        self._set_selected(self.selected_idx + 1)

    def _active_sc(self) -> SmartComplete | None:
        """Get the SmartComplete widget for the currently focused input."""
        w = self.focused
        if not isinstance(w, Input):
            return None

        # Map tag filter input to its SmartComplete widget
        if w.id == "tag-filter":
            try:
                from aliasr.tui.utils.smart_complete import SmartComplete
                return self.query_one("#sc-tag", SmartComplete)
            except Exception:
                return None
        return None

    def action_page_up(self) -> None:
        # Check if a SmartComplete dropdown is active
        sc = self._active_sc()
        if sc and sc.is_dropdown_visible:
            sc.option_list.action_page_up()
            return
        # Normal page up behavior
        self._page(-1)

    def action_page_down(self) -> None:
        # Check if a SmartComplete dropdown is active
        sc = self._active_sc()
        if sc and sc.is_dropdown_visible:
            sc.option_list.action_page_down()
            return
        # Normal page down behavior
        self._page(+1)

    def action_cycle_grid_focus(self) -> None:
        search = self.query_one("#search", Input)
        first_global = self._first_globals_input()
        if not self.globals_panel.display or not first_global:
            search.focus()
            self._select_all(search)
            return
        in_globals = isinstance(self.focused, Input) and str(
            getattr(self.focused, "id", "")
        ).startswith("g-")
        target = search if in_globals else first_global
        target.focus()
        self._select_all(target)

    def action_cycle_filter_focus(self) -> None:
        """Cycle between search input and tag filter input only."""
        search = self.query_one("#search", Input)
        tag_filter = self.query_one("#tag-filter", Input)
        
        # Simply toggle between the two inputs
        if self.focused is tag_filter:
            target = search
        else:
            target = tag_filter
            
        target.focus()
        self._select_all(target)

    def action_cycle_select_focus(self) -> None:
        """Cycle through select widgets and search input."""
        search = self.query_one("#search", Input)
        tag_type_select = self.query_one("#tag-type-select", Select)
        target_select = self.query_one("#target-select", Select) 
        os_select = self.query_one("#os-select", Select)
        
        # Determine which widget is currently focused and cycle to the next
        if self.focused is tag_type_select:
            target = target_select
        elif self.focused is target_select:
            target = os_select
        elif self.focused is os_select:
            target = search
        else:
            # Default to search if focus is elsewhere
            target = tag_type_select
            
        target.focus()
        if isinstance(target, Input):
            self._select_all(target)

    def action_toggle_grid(self) -> None:
        """Toggle globals grid visibility."""
        self.globals_panel.display = not self.globals_panel.display

        def _refresh():
            ev = Resize(self.size, self.size)
            self.title_list.on_resize(ev)
            self.command_list.on_resize(ev)

        self.call_after_refresh(_refresh)

    def action_build_screen(self) -> None:
        if not self.matches:
            return

        cheat = self.matches[self.selected_idx]

        # Check if this command has variations
        from aliasr.core.variations import get_all_variations
        import re

        tokens = re.findall(r"<([^>\s]+)>", cheat.cmd or "")
        param_names = []
        seen = set()
        for tok in tokens:
            name = tok.split("|", 1)[0]
            if name not in seen:
                seen.add(name)
                param_names.append(name)

        variations = get_all_variations(cheat.cmd, param_names)

        def _build_done(result: str | None) -> None:
            if not result:
                return

            # Handle tmux logic...
            if self.app.in_tmux:
                target = self.app.tmux_target_pane
                if target and target.isdigit():
                    from aliasr.core.tmux import get_current_pane
                    if target == get_current_pane():
                        self.app.pending_inject = result
                        self.app.exit()
                        return

                    from aliasr.core.inject import inject
                    inject(
                        cmd=result,
                        using_tmux=True,
                        execute=self.app.execute_cmd,
                        pane_index=target,
                    )
                    return

            self.app.pending_inject = result
            self.app.exit()

        if variations:
            # Has variations - show variations screen first
            def _variations_done(selected: dict[str, str] | None) -> None:
                if not selected:
                    return

                # Apply variations to command
                from aliasr.core.variations import apply_multiple_variations
                modified_cmd = apply_multiple_variations(cheat.cmd, selected)

                # Now open build screen with modified command
                from aliasr.tui.build_screen.build_screen import BuildScreen
                self.app.push_screen(
                    BuildScreen(
                        cheat.title,
                        modified_cmd,
                        Path(cheat.path),
                        cheat.cmd_tags,
                        callback=_build_done,
                    ),
                    _build_done,
                )

            from aliasr.tui.build_screen.variations_screen import VariationsScreen
            self.app.push_screen(VariationsScreen(cheat.cmd, variations), _variations_done)
        else:
            # No variations - go directly to build screen
            from aliasr.tui.build_screen.build_screen import BuildScreen
            self.app.push_screen(
                BuildScreen(
                    cheat.title,
                    cheat.cmd,
                    Path(cheat.path),
                    cheat.cmd_tags,
                    callback=_build_done,
                ),
                _build_done,
            )

    def action_globals_screen(self) -> None:
        self.globals_panel.commit_all_modified()
        prior_visible = self.globals_panel.display
        prev_key = self._focused_global_key()

        def _done(order_changed: bool | None) -> None:
            if order_changed:
                self._remount_globals_grid(prior_visible)
            else:
                self.globals_panel.rebuild_from_store()
            self._refocus_after_globals(prev_key)

        from aliasr.tui.globals_screen.globals_screen import GlobalsScreen
        self.app.push_screen(GlobalsScreen(), _done)

    def action_creds_screen(self) -> None:
        self.globals_panel.commit_all_modified()

        from aliasr.tui.creds_screen.creds_screen import CredsScreen
        self.app.push_screen(CredsScreen())

    def refresh_matches(self) -> None:
        from textual.widgets import Select

        query = self.query_one("#search", Input).value or ""

        # Get filter values from Select widgets
        sb = self.query_one("#search-bar", MainSearch)
        target_value = sb.query_one("#target-select", Select).value
        os_value = sb.query_one("#os-select", Select).value

        # Handle Select.BLANK properly
        target_filter = "" if (target_value is Select.BLANK or target_value is None) else str(target_value)
        os_filter = "" if (os_value is Select.BLANK or os_value is None) else str(os_value)

        # Start with current tag's cheats or all cheats
        pool = self.tag_to_cheats.get(self.current_tag, [])

        # Apply target and OS filters only if they're not empty
        if target_filter or os_filter:
            filtered_pool = []
            for cheat in pool:
                cheat_tags = set(cheat.cheat_tags) | set(cheat.cmd_tags)

                # Check target filter
                if target_filter:
                    target_tag = f"target/{target_filter}"
                    if target_tag not in cheat_tags:
                        continue
                    
                # Check OS filter
                if os_filter:
                    os_tag = f"os/{os_filter}"
                    if os_tag not in cheat_tags:
                        continue

                filtered_pool.append(cheat)
            pool = filtered_pool

        new_matches = self._search_cheats(pool, query)
        if new_matches == getattr(self, "matches", None):
            return
        self.matches = new_matches
        self.selected_idx = 0
        self._sync_lists()
        self._update_header()

    # ---------- Events ----------

    def on_resize(self, _: Resize) -> None:
        if self.title_list.size.height > 1:
            if not self.globals_panel.display and GLOBALS_SHOW_GRID:
                self.globals_panel.display = True
        else:
            if self.globals_panel.display:
                self._focus_search_if_focused_globals()
                self.globals_panel.display = False

    @on(Click, "#title,#command")
    def _focus_search_from_click(self, event: Click) -> None:
        self.query_one("#search", Input).focus()
        event.stop()

    @on(Input.Changed, "#search")
    def _on_search(self, _: Input.Changed) -> None:
        self.refresh_matches()

    @on(Input.Submitted, "#search")
    @on(Input.Submitted, "#globals Input")
    def _submit_from_search(self, event: Input.Submitted) -> None:
        self.action_build_screen()
        event.stop()

    @on(MouseScrollUp)
    def _wheel_up(self, event: MouseScrollUp) -> None:
        self.action_select_previous()
        event.stop()

    @on(MouseScrollDown)
    def _wheel_down(self, event: MouseScrollDown) -> None:
        self.action_select_next()
        event.stop()
