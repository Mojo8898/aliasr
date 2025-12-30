from rich.text import Text
from textual.widgets import Static


class CheatHeader(Static):
    def set_current(self, title: str, cmd_first_line: str) -> None:
        width = (self.size.width if getattr(self, "size", None) else 80) or 80

        def cut(txt: Text) -> Text:
            txt.truncate(width, overflow="ellipsis")
            return txt

        theme = self.app.available_themes.get(self.app.theme)
        title_txt = cut(Text(title or "", style=theme.warning))
        cmd_txt = cut(Text(self._one_line(cmd_first_line), style=theme.foreground))
        self.update(title_txt + Text("\n") + cmd_txt)

    @staticmethod
    def _one_line(val) -> str:
        txt = val.plain if isinstance(val, Text) else str(val or "")
        return txt.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
