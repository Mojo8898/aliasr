from pathlib import Path
from typing import Iterable, Set
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import DirectoryTree, Footer, Input, Static, Tree
from textual.widgets._tree import TreeNode

from aliasr.core.config import kb_root


class SmartTree(DirectoryTree):
    BINDINGS = [
        Binding("right", "smart_expand"),
        Binding("left", "smart_collapse"),
    ]

    def __init__(self, path: str | Path, **kwargs) -> None:
        super().__init__(str(path), **kwargs)
        self._filter = ""
        self._expanded_paths: Set[Path] = set()
        self._selected_path: Path | None = None

    # ---------- State Management ----------

    def _save_state(self) -> None:
        """Save expanded nodes and cursor position before reload."""
        self._expanded_paths.clear()
        self._selected_path = None

        # Save cursor position
        if (
            self.cursor_node
            and hasattr(self.cursor_node, "data")
            and self.cursor_node.data
        ):
            self._selected_path = self.cursor_node.data.path

        # Save expanded nodes
        def collect_expanded(node: TreeNode) -> None:
            if node.is_expanded and hasattr(node, "data") and node.data:
                self._expanded_paths.add(node.data.path)
            for child in node.children:
                collect_expanded(child)

        if self.root:
            collect_expanded(self.root)

    def _restore_state(self) -> None:
        """Restore expanded nodes and cursor position after reload."""
        if not self.root:
            return

        # Expand previously expanded nodes
        nodes_to_process = [self.root]
        cursor_node = None

        while nodes_to_process:
            node = nodes_to_process.pop(0)

            if hasattr(node, "data") and node.data:
                # Check if this node should be expanded
                if node.data.path in self._expanded_paths and node.allow_expand:
                    node.expand()

                # Check if this was the selected node
                if self._selected_path and node.data.path == self._selected_path:
                    cursor_node = node

            # Add children to process (whether expanded or not, to find cursor)
            nodes_to_process.extend(node.children)

        # Restore cursor position
        if cursor_node:
            self.cursor_line = cursor_node.line

    # ---------- Filter ----------

    def set_filter(self, filter: str) -> None:
        """Apply filter while preserving tree state."""
        new_filter = (filter or "").lower()
        if new_filter == self._filter:
            return

        self._save_state()
        self._filter = new_filter

        # Schedule reload with state restoration
        async def _reload_with_state():
            await self.reload()
            self.call_after_refresh(self._restore_state)

        self.call_next(_reload_with_state)

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        q = self._filter
        if not q:
            return paths
        return (p for p in paths if p.is_dir() or q in p.name.lower())

    # ---------- Smart Nav ----------

    def action_smart_expand(self) -> None:
        n = self.cursor_node
        if n and n.allow_expand and not n.is_expanded:
            self.action_toggle_node()
        else:
            self.action_cursor_down()

    def _goto_parent(self) -> None:
        cur = Path(self.path).resolve()
        par = cur.parent
        if par != cur and par.is_dir():
            self._save_state()
            self.path = str(par)

            async def _reload_and_expand():
                await self.reload()
                if self.root:
                    self.root.expand()
                self._restore_state()

            self.call_after_refresh(_reload_and_expand)

    def action_smart_collapse(self) -> None:
        n = self.cursor_node
        if not n:
            return
        if n.is_root:
            if n.is_expanded:
                self.action_toggle_node()
            else:
                self._goto_parent()
        elif n.is_expanded:
            self.action_toggle_node()
        else:
            self.action_cursor_parent()

    @on(Tree.NodeCollapsed)
    async def _root_collapsed(self, event: Tree.NodeCollapsed) -> None:
        if event.node.is_root:
            event.stop()
            self._goto_parent()


class TreeScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel"),
        Binding(kb_root("tree_screen"), "cancel"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static("Choose a file", id="title")
            yield Input(placeholder="Filter visible paths for files...", id="filter")
            yield SmartTree(path=Path.cwd(), id="tree")

    # ---------- Actions ----------

    def action_cancel(self) -> None:
        self.dismiss(None)

    # ---------- Events ----------

    def on_mount(self) -> None:
        self.query_one("#tree", SmartTree).focus()

    @on(Input.Changed, "#filter")
    def _filter_changed(self, e: Input.Changed) -> None:
        self.query_one("#tree", SmartTree).set_filter(e.value)

    @on(DirectoryTree.FileSelected)
    def _file_selected(self, e: DirectoryTree.FileSelected) -> None:
        e.stop()
        self.dismiss(str(e.path))
