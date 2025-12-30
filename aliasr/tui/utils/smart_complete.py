from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from textual.css.query import NoMatches
from textual.events import MouseScrollUp, MouseScrollDown
from textual.geometry import Offset, Region, Spacing
from textual.widgets import Input
from textual_autocomplete import (
    AutoComplete,
    DropdownItem,
    PathAutoComplete,
    TargetState,
)


class SmartComplete(AutoComplete):
    """
    '/'  -> path at '/'
    '.'  -> path at cwd()
    '~'  -> path at home()
    else -> regular candidates (list or callback)
    """

    def __init__(
        self,
        target: Input,
        candidates: Iterable[str | DropdownItem]
        | Callable[[TargetState], Sequence[DropdownItem]]
        | None = None,
        *,
        path_kwargs: dict | None = None,
        dropdown_class: str | None = None,
        on_completed: Callable[[str], None] | None = None,
        enable_paths: bool = True,
        always_open: bool = False,
        focus_next_on_complete: bool = False,
        submit_on_complete: bool = False,
        additional_width: int = 0,
        additional_height: int = 0,
        **kwargs: Any,
    ) -> None:
        super().__init__(target=target, candidates=None, **kwargs)
        self._candidates = candidates
        self._path_kwargs = dict(path_kwargs or {})
        self._path_ac = PathAutoComplete(
            target=target, path=Path.cwd(), **self._path_kwargs
        ) if enable_paths else None
        self._dropdown_class = dropdown_class
        self._on_completed = on_completed
        self._enable_paths = enable_paths
        self._always_open = always_open
        self._additional_width = additional_width
        self._additional_height = additional_height
        self._focus_next_on_complete = focus_next_on_complete
        self._submit_on_complete = submit_on_complete

    # ---------- UI ----------

    def on_mount(self) -> None:
        try:
            if self._dropdown_class:
                self.option_list.add_class(self._dropdown_class)
        except NoMatches:
            pass
        if self._always_open:
            # Watch the target's focus state
            def on_focus_change() -> None:
                if self.target and self.target.has_focus:
                    self.call_after_refresh(self.action_show)

            self.watch(self.target, "has_focus", on_focus_change)

    # ---------- Helpers ----------

    @property
    def is_dropdown_visible(self) -> bool:
        """Check if dropdown is currently visible."""
        try:
            return (
                self.option_list.display
                and not self.option_list.disabled
                and getattr(self.option_list, "option_count", 0) > 0
            )
        except (NoMatches, AttributeError):
            return False

    @staticmethod
    def _mode(text: str) -> str:
        if text.startswith("/"):
            return "root"
        if text.startswith("~"):
            return "home"
        if text.startswith("."):
            return "cwd"
        return "regular"

    def _home_state(self, state: TargetState) -> TargetState:
        text = state.text
        pos = state.cursor_position
        if text.startswith("~/"):
            return TargetState(text=text[2:], cursor_position=max(0, pos - 2))
        if text.startswith("~"):
            return TargetState(text=text[1:], cursor_position=max(0, pos - 1))
        return state

    def _regular_candidates(self, state: TargetState) -> list[DropdownItem]:
        src = self._candidates
        if src is None:
            return []
        if callable(src):
            items = src(state)
            return [
                i if isinstance(i, DropdownItem) else DropdownItem(str(i))
                for i in items
            ]
        return [i if isinstance(i, DropdownItem) else DropdownItem(str(i)) for i in src]

    def _split_prefix(self, text: str) -> tuple[str, str]:
        if text.startswith("~/"):
            return "~/", text[2:]
        if text.startswith("~"):
            return "~", text[1:]
        if text.startswith("./"):
            return "./", text[2:]
        if text.startswith("."):
            return ".", text[1:]
        if text.startswith("/"):
            return "/", text[1:]
        return "", text

    def _restore_prefix(self, committed: str, prefix: str) -> str:
        if not prefix:
            return committed
        if prefix == "~/":
            return (
                committed
                if committed.startswith("~/")
                else "~/" + committed.lstrip("/")
            )
        if prefix == "~":
            return (
                committed
                if committed.startswith("~/")
                else "~/" + committed.lstrip("/")
            )
        if prefix in (".", "./"):
            if committed.startswith("./"):
                return committed
            return "./" + committed.lstrip("/")
        if prefix == "/":
            return committed if committed.startswith("/") else "/" + committed
        return committed

    def _configure_path(self, mode: str) -> None:
        if not self._path_ac:
            return
        if mode == "root":
            self._path_ac.path = Path("/")
        elif mode == "home":
            self._path_ac.path = Path.home()
        else:
            self._path_ac.path = Path.cwd()

    # ---------- Overrides ----------

    def get_candidates(self, state):
        if self._enable_paths and self._mode(state.text) != "regular":
            pfx, stripped = self._split_prefix(state.text)
            if pfx:
                mode = (
                    "home"
                    if pfx.startswith("~")
                    else ("root" if pfx.startswith("/") else "cwd")
                )
                self._configure_path(mode)
                return self._path_ac.get_candidates(
                    TargetState(stripped, max(0, state.cursor_position - len(pfx)))
                )
        return self._regular_candidates(state)

    def get_search_string(self, state):
        if self._enable_paths and self._mode(state.text) != "regular":
            pfx, stripped = self._split_prefix(state.text)
            if pfx:
                mode = (
                    "home"
                    if pfx.startswith("~")
                    else ("root" if pfx.startswith("/") else "cwd")
                )
                self._configure_path(mode)
                s = TargetState(stripped, max(0, state.cursor_position - len(pfx)))
                return self._path_ac.get_search_string(s)
        return state.text[: state.cursor_position]

    def apply_completion(self, value, state):
        pfx, stripped = self._split_prefix(state.text)
        if not pfx:
            super().apply_completion(value, state)
            committed = self.target.value
        else:
            mode = (
                "home"
                if pfx.startswith("~")
                else ("root" if pfx.startswith("/") else "cwd")
            )
            self._configure_path(mode)
            s = TargetState(stripped, max(0, state.cursor_position - len(pfx)))
            self._path_ac.apply_completion(value, s)

            committed = self._restore_prefix(self.target.value, pfx)
            if committed != self.target.value:
                self.target.value = committed
            self.target.cursor_position = len(committed)

        if committed.endswith("/"):
            self.action_show()
        else:
            super().post_completion()

        if self._on_completed:
            self._on_completed(committed)

        if self._focus_next_on_complete:
            self.app.action_focus_next()

        if self._submit_on_complete:
            def _submit():
                # Ensure the target has focus first
                if not self.target.has_focus:
                    self.target.focus()
                # Post the Submitted event directly
                self.target.post_message(self.target.Submitted(self.target, self.target.value))

            self.call_after_refresh(_submit)

    def should_show_dropdown(self, search_string: str) -> bool:
        if self._always_open and not self.target.has_focus:
            return False

        try:
            if self.target.region.width <= 0 or self.target.region.height <= 0:
                return False
        except Exception:
            return False

        if self._always_open:
            return True

        try:
            default = super().should_show_dropdown(search_string)
        except NoMatches:
            return False
        text = getattr(self.target, "value", "") or ""
        mode = self._mode(text)
        if mode == "regular":
            return default
        return default or (search_string == "" and text != "")

    def post_completion(self) -> None:
        text = getattr(self.target, "value", "") or ""
        if text.endswith("/"):
            self.action_show()
            return
        return super().post_completion()

    # ---------- Actions ----------

    def action_show(self) -> None:
        try:
            if self.target.region.width <= 0 or self.target.region.height <= 0:
                return
        except Exception:
            return
        super().action_show()

    def on_mouse_scroll_up(self, event: MouseScrollUp) -> None:
        """Stop scroll propagation when over the dropdown."""
        if self.is_dropdown_visible:
            try:
                # Check if mouse is over the option list
                if self.option_list.region.contains(event.screen_x, event.screen_y):
                    from textual.actions import SkipAction
                    try:
                        self.option_list.action_scroll_up()
                    except SkipAction:
                        pass  # Can't scroll, that's fine
                    event.stop()
            except (NoMatches, AttributeError):
                pass

    def on_mouse_scroll_down(self, event: MouseScrollDown) -> None:
        """Stop scroll propagation when over the dropdown."""
        if self.is_dropdown_visible:
            try:
                # Check if mouse is over the option list
                if self.option_list.region.contains(event.screen_x, event.screen_y):
                    from textual.actions import SkipAction
                    try:
                        self.option_list.action_scroll_down()
                    except SkipAction:
                        pass  # Can't scroll, that's fine
                    event.stop()
            except (NoMatches, AttributeError):
                pass

    # ---------- Alignment Overrides ----------

    def _align_to_target(self) -> None:
        try:
            dropdown = self.option_list
        except NoMatches:
            return

        x = self.target.region.x
        y = self.target.region.y + self.target.region.height + self._additional_height

        dropdown.styles.width = self.target.region.width + self._additional_width
        dropdown.styles.height = "auto"
        dropdown.styles.max_height = 10

        width, height = dropdown.outer_size
        x, y, _w, _h = Region(x, y, width, height).constrain(
            "inside", "none", Spacing.all(0), self.screen.scrollable_content_region
        )
        self.absolute_offset = Offset(x, y)
        self.refresh(layout=True)

    # ---------- Guard Rebuild/Teardown ----------

    def _rebuild_options(self, target_state: TargetState, search_string: str) -> None:
        try:
            super()._rebuild_options(target_state, search_string)
            try:
                if getattr(self.option_list, "option_count", 0) == 0:
                    self.action_hide()
            except NoMatches:
                pass
        except NoMatches:
            return

    def on_unmount(self) -> None:
        try:
            self.action_hide()
        except Exception:
            pass
