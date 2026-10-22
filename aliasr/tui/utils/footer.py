"""Footer that skips a redundant double restyle of every key."""

from textual.app import ComposeResult
from textual.widgets import Footer as _Footer
from textual.widgets._footer import FooterKey


class Footer(_Footer):
    """Textual's Footer, minus two wasted restyles per key on each (re)compose.

    FooterKey.compact defaults to True but Footer.compact to False, so every
    bound key's watcher adds then removes -compact, each a full restyle (~10 ms
    at startup, and again whenever focus changes the bindings). Presetting the
    bound value silently skips both. The command-palette key isn't bound to
    Footer.compact, so it keeps its default.
    """

    def compose(self) -> ComposeResult:
        for widget in super().compose():
            if isinstance(widget, FooterKey) and not widget.has_class(
                "-command-palette"
            ):
                widget.set_reactive(FooterKey.compact, self.compact)
                widget.set_class(self.compact, "-compact", update=False)
            yield widget
