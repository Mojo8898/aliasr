import re

from rich.text import Text
from textual.widgets import Static


class CheatList(Static):
    """Base class for cheat list widgets (titles/commands)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.top = 0
        self.selected = 0
        self.cheats: list = []

    # ---------- Helpers ----------

    def _one_line(self, val) -> str:
        txt = val.plain if isinstance(val, Text) else str(val or "")
        txt = txt.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
        txt = re.sub(r"\s+", " ", txt)
        return txt

    def _rows(self) -> int:
        return max(1, int(self.content_size.height))

    def _clamp(self, n: int, lo: int, hi: int) -> int:
        return max(lo, min(hi, n))

    def _reframe(self) -> None:
        """Ensure selected is visible; keep top within bounds."""
        n = len(self.cheats)
        if not n:
            self.top = 0
            return
        rows = self._rows()
        max_top = max(0, n - rows)

        if self.selected < self.top:
            self.top = self.selected
        elif self.selected >= self.top + rows:
            self.top = self.selected - rows + 1

        self.top = self._clamp(self.top, 0, max_top)

    def _refresh(self) -> None:
        """Render current window."""
        n = len(self.cheats)
        if not n:
            self.update("")
            return

        rows = self._rows()
        start = self.top
        end = min(n, start + rows)
        width = (self.size.width or 80) if self.size else 80

        out = Text()
        for i in range(start, end):
            raw = self._one_line(self._item_text(self.cheats[i]))
            theme = self.app.available_themes.get(self.app.theme)
            line = Text(raw, style=theme.foreground if i == self.selected else None)
            line.truncate(width, overflow="ellipsis")
            out.append(line)
            if i < end - 1:
                out.append("\n")
        self.update(out)

    # ---------- Public API ----------

    def visible_rows(self) -> int:
        return self._rows()

    def set_list(self, cheats, selected: int = 0) -> None:
        self.cheats = list(cheats)
        self.selected = (
            0 if not self.cheats else self._clamp(selected, 0, len(self.cheats) - 1)
        )
        self.top = 0
        self._reframe()
        self._refresh()

    def set_selected(self, index: int) -> None:
        if not self.cheats:
            self.update("")
            return
        self.selected = self._clamp(index, 0, len(self.cheats) - 1)
        self._reframe()
        self._refresh()

    def page_to(self, top: int, place: str = "top") -> None:
        """Scroll to `top`; select first/last visible row depending on `place`."""
        n = len(self.cheats)
        if not n:
            self.update("")
            return
        rows = self._rows()
        self.top = self._clamp(top, 0, max(0, n - rows))
        self.selected = self.top if place == "top" else min(n - 1, self.top + rows - 1)
        self._reframe()
        self._refresh()

    def on_resize(self, _) -> None:
        self._reframe()
        self._refresh()

    def _item_text(self, c) -> str:  # override in subclasses
        return str(c)


class CheatTitleList(CheatList):
    def _item_text(self, c) -> str:
        return c.title


class CheatCommandList(CheatList):
    def _item_text(self, c) -> str:
        return c.cmd
