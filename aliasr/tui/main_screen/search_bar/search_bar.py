from textual import on
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.widgets import Input, Static, Tab, Tabs, Select

from aliasr.core.config import CHEATS_DEFAULT_GROUPING, kb_root
from aliasr.tui.utils.common import widget_id
from aliasr.tui.utils.smart_complete import SmartComplete
from aliasr.tui.main_screen.search_bar.indicators import Indicators


class CheatTags(Tabs):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._id_to_tag = {}
        self._all_tags = []
        self._current_tag_query = ""
        self._target_filter = ""
        self._os_filter = ""
        self._tag_type_filter = ""

    # ---------- Helpers ----------

    def _get_visible_tags(self, tags: list[str]) -> list[str]:
        """Get tags that match the current filters and tag query"""
        visible = []

        for tag in tags:
            # Check tag query filter (including "all")
            if self._current_tag_query:
                # Allow filtering of "all" tag
                if tag.lower() == "all":
                    if self._current_tag_query not in "all":
                        continue
                else:
                    # Extract display name for filtering
                    _, _, display_name = tag.rpartition("/")
                    if not display_name:
                        display_name = tag
                    if self._current_tag_query not in display_name.lower():
                        continue

            visible.append(tag)

        return visible

    def _filter_by_type(self, tag: str) -> bool:
        """Check if a tag should be shown based on tag type filter."""
        # If no type filter is set (blank/empty), show all tags
        if not self._tag_type_filter:
            return True

        if tag.lower() == "all":
            return True  # Always show "all" regardless of type filter

        # Dynamic check based on prefix
        if "/" in tag:
            tag_prefix = tag.split("/")[0]
            return tag_prefix == self._tag_type_filter

        return False

    # ---------- Public API ----------

    def set_tags(self, tags: list[str], current: str) -> None:
        self.clear()
        self._all_tags = tags  # Store ALL tags
        self._id_to_tag.clear()

        # Only create tabs for tags we want to show initially
        # But keep all tags in _all_tags for filtering
        for full_tag in tags:
            tid = widget_id("tab-", full_tag)
            self._id_to_tag[tid] = full_tag

            # Display just the tag name, not the prefix
            if full_tag == "all":
                display_name = "all"
            else:
                _, _, display_name = full_tag.rpartition("/")
                if not display_name:
                    display_name = full_tag

            self.add_tab(Tab(display_name, id=tid))

        desired = current if current in tags else (tags[0] if tags else "")
        desired_id = widget_id("tab-", desired) if desired else ""
        self.call_after_refresh(lambda: setattr(self, "active", desired_id))

    def apply_filters(
        self,
        target_filter: str = "",
        os_filter: str = "",
        tag_query: str = "",
        tag_type_filter: str = "",
    ) -> None:
        """Apply all filters to tabs"""
        # Handle Select.BLANK values
        from textual.widgets import Select

        if target_filter is Select.BLANK or target_filter is None:
            target_filter = ""
        if os_filter is Select.BLANK or os_filter is None:
            os_filter = ""
        if tag_type_filter is Select.BLANK or tag_type_filter is None:
            tag_type_filter = ""

        self._target_filter = str(target_filter).lower()
        self._os_filter = str(os_filter).lower()
        self._current_tag_query = (tag_query or "").lower()
        self._tag_type_filter = str(tag_type_filter).lower()

        # Get the screen to check which cheats match filters
        scr = self.app.screen
        if not scr or scr.__class__.__name__ != "MainScreen":
            # Just apply tag query and type filters
            visible = self._get_visible_tags(self._all_tags)
            for tid, name in self._id_to_tag.items():
                if name in visible and self._filter_by_type(name):
                    self.show(tid)
                else:
                    self.hide(tid)
            return

        # Build set of tags that have matching cheats
        matching_tags = set()
        all_cheats = getattr(self.app, "cheats", [])
        protected_prefixes = {"target/", "os/"}

        for cheat in all_cheats:
            # Check if cheat matches target and OS filters
            cheat_tags = set(cheat.cheat_tags) | set(cheat.cmd_tags)

            # Check target filter
            if self._target_filter:
                target_tag = f"target/{self._target_filter}"
                if target_tag not in cheat_tags:
                    continue

            # Check OS filter
            if self._os_filter:
                os_tag = f"os/{self._os_filter}"
                if os_tag not in cheat_tags:
                    continue

            # This cheat matches, add its tags
            for tag in cheat_tags:
                # Skip protected tags
                if any(tag.startswith(p) for p in protected_prefixes):
                    continue

                # If no type filter, add all tags
                # If type filter is set, only add tags of that type
                if not self._tag_type_filter:
                    matching_tags.add(tag)
                elif "/" in tag:
                    tag_prefix = tag.split("/")[0]
                    if tag_prefix == self._tag_type_filter:
                        matching_tags.add(tag)

        # Track which tabs will be visible
        visible_tabs = set()
        current_active = self.active

        # Show/hide tabs based on matching tags and filters
        for tid, tag in self._id_to_tag.items():
            should_show = False

            if tag == "all":
                # Check tag query for "all"
                if not self._current_tag_query or self._current_tag_query in "all":
                    should_show = True
            elif tag in matching_tags:
                # Check tag query
                _, _, display_name = tag.rpartition("/")
                if (
                    not self._current_tag_query
                    or self._current_tag_query in display_name.lower()
                ):
                    should_show = True

            if should_show:
                self.show(tid)
                visible_tabs.add(tid)
            else:
                self.hide(tid)

        # Handle case where no tabs match - always show "all" as fallback
        all_id = widget_id("tab-", "all")
        if not visible_tabs and all_id in self._id_to_tag:
            self.show(all_id)
            visible_tabs.add(all_id)

        # If current active tab is hidden, switch to a visible one
        if current_active and current_active not in visible_tabs:
            # Prefer "all" tab if visible
            if all_id in visible_tabs:
                self.active = all_id
            # Otherwise pick the first visible tab
            elif visible_tabs:
                self.active = next(iter(visible_tabs))


class MainSearch(Vertical):
    BINDINGS = [
        Binding(kb_root("prev_tab"), "prev_tab"),
        Binding(kb_root("next_tab"), "next_tab"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._suppress_focus_on_tab_change = False
        self._tag_types = []

    # ---------- UI ----------

    def compose(self):
        with Horizontal(id="tabs-row"):
            yield CheatTags(id="tabs")
            with Horizontal(id="filter-group"):
                yield Static("Filter:", id="filter-label")

                # Tag filter input
                tag_input = Input(placeholder="Tag...", id="tag-filter")
                yield tag_input

                # Tag type select
                yield Select(
                    [],  # Will be populated dynamically
                    id="tag-type-select",
                    prompt="Type",
                    allow_blank=True,
                    compact=True,
                )

                # Target select
                yield Select(
                    [
                        ("Remote", "remote"),
                        ("Local", "local"),
                    ],
                    id="target-select",
                    prompt="Target",
                    allow_blank=True,
                    compact=True,
                )

                # OS select
                yield Select(
                    [
                        ("Linux", "linux"),
                        ("Windows", "windows"),
                    ],
                    id="os-select",
                    prompt="OS",
                    allow_blank=True,
                    compact=True,
                )

        with Horizontal(id="search-container"):
            yield Input(placeholder="Search for a command...", id="search")
            yield Indicators(id="indicators")

        yield SmartComplete(
            target=tag_input,
            candidates=lambda _: self._get_tag_candidates(),
            dropdown_class="sc-tag",
            enable_paths=False,
            always_open=False,
            on_completed=lambda _: self._apply_filters(),
            submit_on_complete=True,
            id="sc-tag",
        )

    def on_mount(self) -> None:
        # Build caches once at mount time
        tabs = self.query_one("#tabs", CheatTags)
        tag_names = set()

        for tag in tabs._all_tags:
            if tag != "all":
                # Extract the tag name part from any prefix
                _, _, name = tag.rpartition("/")
                if name:
                    tag_names.add(name)

        self._all_tag_names = sorted(tag_names)

    # ---------- Helpers ----------

    def _main_screen(self):
        scr = self.app.screen
        return scr if scr.__class__.__name__ == "MainScreen" else None

    def _get_tag_candidates(self) -> list[str]:
        """Get tag names that match current filters."""
        from textual.widgets import Select

        # Get filter values and handle Select.BLANK
        target_value = self.query_one("#target-select", Select).value
        os_value = self.query_one("#os-select", Select).value
        tag_type_value = self.query_one("#tag-type-select", Select).value

        target_filter = (
            ""
            if (target_value is Select.BLANK or target_value is None)
            else str(target_value)
        )
        os_filter = (
            "" if (os_value is Select.BLANK or os_value is None) else str(os_value)
        )
        tag_type_filter = (
            ""
            if (tag_type_value is Select.BLANK or tag_type_value is None)
            else str(tag_type_value)
        )

        # Get all tags of the selected type
        matching_tags = set()
        all_cheats = getattr(self.app, "cheats", [])

        # Add "all" as a candidate
        matching_tags.add("all")

        for cheat in all_cheats:
            # Check if cheat matches target and OS filters
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

            # This cheat matches, add its tags based on type filter
            for tag in cheat_tags:
                if "/" not in tag or tag.startswith(("target/", "os/")):
                    continue

                tag_prefix = tag.split("/")[0]

                # If no type filter or matching type
                if not tag_type_filter or tag_type_filter == tag_prefix:
                    _, _, name = tag.rpartition("/")
                    if name:
                        matching_tags.add(name)

        return sorted(matching_tags)

    def _apply_filters(self) -> None:
        """Apply all filters (target, OS, and tag)."""
        from textual.widgets import Select

        tabs = self.query_one("#tabs", CheatTags)

        # Get filter values, handling Select.BLANK properly
        target_value = self.query_one("#target-select", Select).value
        os_value = self.query_one("#os-select", Select).value
        tag_type_value = self.query_one("#tag-type-select", Select).value

        # Convert Select.BLANK to empty string
        target_filter = (
            ""
            if (target_value is Select.BLANK or target_value is None)
            else str(target_value)
        )
        os_filter = (
            "" if (os_value is Select.BLANK or os_value is None) else str(os_value)
        )
        tag_type_filter = (
            ""
            if (tag_type_value is Select.BLANK or tag_type_value is None)
            else str(tag_type_value)
        )
        tag_filter = self.query_one("#tag-filter", Input).value or ""

        # Apply filters to tabs
        tabs.apply_filters(target_filter, os_filter, tag_filter, tag_type_filter)

        # Update the main screen's current tag if needed
        scr = self._main_screen()
        if scr:
            # Check if current tag is still visible
            current_active = tabs.active
            if current_active and current_active in tabs._id_to_tag:

                # If current tag is hidden, switch to "all" or first visible
                try:
                    tab_widget = tabs.query_one(f"#{current_active}", Tab)
                    if not getattr(tab_widget, "display", True):
                        # Find first visible tab
                        visible_tabs = [
                            t for t in tabs.query(Tab) if getattr(t, "display", True)
                        ]
                        if visible_tabs:
                            tabs.active = visible_tabs[0].id
                            scr.current_tag = tabs._id_to_tag.get(
                                visible_tabs[0].id, "all"
                            )
                except Exception:
                    pass

            # Refresh matches with the filters
            scr.refresh_matches()

    # ---------- Actions ----------

    def action_prev_tab(self) -> None:
        self.query_one("#tabs", CheatTags).action_previous_tab()

    def action_next_tab(self) -> None:
        self.query_one("#tabs", CheatTags).action_next_tab()

    # ---------- Events ----------

    @on(Input.Changed, "#search")
    def _search_changed(self, _):
        scr = self._main_screen()
        if scr:
            scr.refresh_matches()

    @on(Tabs.TabActivated, "#tabs")
    def _tag_changed(self, event: Tabs.TabActivated) -> None:
        scr = self._main_screen()
        if not scr:
            return
        tabs = self.query_one("#tabs", CheatTags)
        original_tag = tabs._id_to_tag.get(event.tab.id, event.tab.id)
        scr.current_tag = original_tag
        self.call_after_refresh(scr.refresh_matches)
        tag_filter = self.query_one("#tag-filter", Input)
        if self._suppress_focus_on_tab_change or tag_filter.has_focus:
            return
        self.query_one("#search", Input).focus()

    @on(Input.Submitted, "#tag-filter")
    def _tag_search_submitted(self, event: Input.Submitted) -> None:
        # Simply focus the search input
        self.query_one("#search", Input).focus()
        event.stop()

    @on(Select.Changed, "#target-select")
    def _target_filter_changed(self, _: Select.Changed) -> None:
        self._apply_filters()

    @on(Select.Changed, "#os-select")
    def _os_filter_changed(self, _: Select.Changed) -> None:
        self._apply_filters()

    @on(Select.Changed, "#tag-type-select")
    def _tag_type_filter_changed(self, _: Select.Changed) -> None:
        self._apply_filters()

    @on(Input.Changed, "#tag-filter")
    def _tag_filter_changed(self, event: Input.Changed) -> None:
        # Apply filters first
        self._apply_filters()

        # If filter is now empty, automatically select "all" tab
        if not event.value.strip():
            tabs = self.query_one("#tabs", CheatTags)
            all_id = widget_id("tab-", "all")

            # Check if "all" tab is visible
            try:
                all_tab = tabs.query_one(f"#{all_id}", Tab)
                if getattr(all_tab, "display", True):
                    tabs.active = all_id
            except Exception:
                pass

    # ---------- Public API ----------

    def build_dynamic_tag_types(self) -> None:
        """Dynamically determine tag types from available tags."""
        tabs = self.query_one("#tabs", CheatTags)
        protected_prefixes = {"target/", "os/"}

        # Find all unique prefixes
        prefixes = set()
        for tag in tabs._all_tags:
            if tag != "all" and "/" in tag:
                prefix = tag.split("/")[0]
                full_prefix = f"{prefix}/"
                if full_prefix not in protected_prefixes:
                    prefixes.add(prefix)

        # Sort prefixes for consistent ordering
        self._tag_types = sorted(prefixes)

        # Update the Select widget with dynamic options (no "All")
        tag_type_select = self.query_one("#tag-type-select", Select)

        options = []
        for prefix in self._tag_types:
            display_name = prefix.capitalize()
            options.append((display_name, prefix))

        tag_type_select.set_options(options)

        if CHEATS_DEFAULT_GROUPING:
            # Check if the configured default exists in the options
            if CHEATS_DEFAULT_GROUPING.lower() in self._tag_types:
                tag_type_select.value = CHEATS_DEFAULT_GROUPING.lower()
                # Apply the filter with this default if it exists
                self._apply_filters()
