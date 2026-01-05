from pathlib import Path
import rignore
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.fuzzy import Matcher
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from aliasr.core.config import RIGNORE, kb_root


class TreeFilterInput(Input):
    """Input widget for filtering files."""

    pass


class TreeScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel"),
        Binding(kb_root("tree_screen"), "cancel"),
        Binding("up", "list_up"),
        Binding("down", "list_down"),
        Binding("pageup", "list_page_up"),
        Binding("pagedown", "list_page_down"),
    ]

    def __init__(self, initial_path: str = "") -> None:
        super().__init__()

        # Use provided path if valid, otherwise use current directory
        if initial_path:
            try:
                path = Path(initial_path).expanduser().resolve()
                if path.is_dir():
                    self._current_path = path
                elif path.is_file():
                    # If it's a file, use its parent directory
                    self._current_path = path.parent
                else:
                    # Not a valid path - use current directory
                    self._current_path = Path.cwd().resolve()
            except (OSError, ValueError):
                # Invalid path - use current directory
                self._current_path = Path.cwd().resolve()
        else:
            self._current_path = Path.cwd().resolve()
        self._all_files: list[Path] = []
        self._current_filter = ""

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static(self._make_title(), id="title")
            yield TreeFilterInput(placeholder="Search files...", id="filter")
            yield OptionList(id="file-list")

    def _make_title(self) -> str:
        return f"Choose a file: {self._current_path}"

    def _scan_files(self) -> list[Path]:
        """Recursively scan all files in current directory."""
        files = []
        try:
            # Use rignore for fast, gitignore-aware file walking
            for entry in rignore.Walker(
                str(self._current_path),
                ignore_hidden=RIGNORE.ignore_hidden,
                read_ignore_files=RIGNORE.read_ignore_files,
                read_parents_ignores=RIGNORE.read_parents_ignores,
                read_git_ignore=RIGNORE.read_git_ignore,
                read_global_git_ignore=RIGNORE.read_global_git_ignore,
                read_git_exclude=RIGNORE.read_git_exclude,
                require_git=RIGNORE.require_git,
                additional_ignores=RIGNORE.additional_ignores,
                additional_ignore_paths=RIGNORE.additional_ignore_paths,
                overrides=RIGNORE.overrides,
                max_depth=RIGNORE.max_depth,
                max_filesize=RIGNORE.max_filesize,
                follow_links=RIGNORE.follow_links,
                case_insensitive=RIGNORE.case_insensitive,
                same_file_system=RIGNORE.same_file_system,
            ):
                file_path = Path(entry)
                if file_path.is_file():
                    files.append(file_path)
        except Exception:
            # Fallback to pathlib if rignore fails
            try:
                for item in self._current_path.rglob("*"):
                    if item.is_file():
                        files.append(item)
            except (PermissionError, OSError):
                pass
        return sorted(files)

    def _populate_list(self, filter_query: str = "") -> None:
        """Populate the file list with optional fuzzy matching and highlighting."""
        file_list = self.query_one("#file-list", OptionList)
        file_list.clear_options()

        if not self._all_files:
            return

        # Get relative paths
        relative_files = []
        for f in self._all_files:
            try:
                rel = f.relative_to(self._current_path)
                relative_files.append((str(rel), f))
            except ValueError:
                continue

        # Apply filter with fuzzy matching
        if filter_query.strip():
            matcher = Matcher(filter_query, case_sensitive=False)
            scored = []
            for rel_str, full_path in relative_files:
                score = matcher.match(rel_str)
                if score > 0:
                    scored.append((score, rel_str, full_path))
            scored.sort(key=lambda x: x[0], reverse=True)
            # Limit to 500 results for performance
            display_files = scored[:500]
        else:
            # Limit to 500 files when no filter
            display_files = [(0, rel, fp) for rel, fp in relative_files[:500]]

        # Add options with highlighting
        if filter_query.strip():
            matcher = Matcher(filter_query, case_sensitive=False)
            for score, rel_str, full_path in display_files:
                # Use matcher.highlight() to get Rich Text with styling
                highlighted_text = matcher.highlight(rel_str)
                file_list.add_option(Option(highlighted_text, id=str(full_path)))
        else:
            for score, rel_str, full_path in display_files:
                file_list.add_option(Option(rel_str, id=str(full_path)))

        if file_list.option_count > 0:
            file_list.highlighted = 0

    # ---------- Actions ----------

    def action_list_up(self) -> None:
        file_list = self.query_one("#file-list", OptionList)
        file_list.action_cursor_up()

    def action_list_down(self) -> None:
        file_list = self.query_one("#file-list", OptionList)
        file_list.action_cursor_down()

    def action_list_page_up(self) -> None:
        file_list = self.query_one("#file-list", OptionList)
        file_list.action_page_up()

    def action_list_page_down(self) -> None:
        file_list = self.query_one("#file-list", OptionList)
        file_list.action_page_down()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        """Submit the currently selected file."""
        file_list = self.query_one("#file-list", OptionList)
        if file_list.highlighted is not None:
            option = file_list.get_option_at_index(file_list.highlighted)
            if option and option.id:
                self.dismiss(option.id)
        else:
            self.dismiss(None)

    # ---------- Events ----------

    def on_mount(self) -> None:
        """Initialize the file picker."""
        file_list = self.query_one("#file-list", OptionList)
        file_list.can_focus = False
        self._all_files = self._scan_files()
        self._populate_list()
        self.query_one("#filter", TreeFilterInput).focus()

    @on(Input.Changed, "#filter")
    def _filter_changed(self, event: Input.Changed) -> None:
        """Update file list based on filter."""
        self._current_filter = event.value or ""
        self._populate_list(self._current_filter)

    @on(Input.Submitted, "#filter")
    def _filter_submitted(self, _: Input.Submitted) -> None:
        """Submit when enter is pressed in filter."""
        self.action_submit()

    @on(OptionList.OptionSelected, "#file-list")
    def _file_selected(self, event: OptionList.OptionSelected) -> None:
        """Handle file selection from list."""
        if event.option.id:
            self.dismiss(event.option.id)
