from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static


class ConfirmDelete(ModalScreen[bool]):
    """A tiny yes/no gate before a destructive delete.

    Only ``y`` confirms; ``n``/escape cancel and any other key is ignored — so a
    stray Enter (or anything else) can never confirm a deletion by accident,
    which is the whole point of the prompt.
    """

    BINDINGS = [
        Binding("y", "confirm"),
        Binding("n", "cancel"),
        Binding("escape", "cancel"),
    ]

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            yield Static(self._message, id="confirm-msg")
            yield Static("[b]y[/] delete    [b]n[/] cancel", id="confirm-hint")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
