from textual.binding import Binding
from aliasr.core.config import kb_grid_nav


GRID_NAV_BINDINGS = [
    Binding(
        kb_grid_nav(f"move_{d}"),
        f"grid_nav('{d}')",
    )
    for d in (
        "left",
        "right",
        "up",
        "down",
    )
]


def grid_nav(
    container, direction: str, *, grid_selector: str, item_selector: str, cols: int
) -> None:
    """Move focus within a logical grid with wrap and ragged last row support."""
    items = list(container.query(f"{grid_selector} {item_selector}"))
    if not items:
        return

    try:
        idx = next(i for i, w in enumerate(items) if getattr(w, "has_focus", False))
    except StopIteration:
        items[0].focus()
        return

    total = len(items)
    rows = (total + cols - 1) // cols
    row, col = divmod(idx, cols)

    def last_in_row(r: int) -> int:
        end = min((r + 1) * cols, total)
        return end - 1

    new_idx = idx
    match direction:
        case "right":
            new_idx = idx + 1 if (col < cols - 1 and idx + 1 < total) else row * cols

        case "left":
            new_idx = idx - 1 if col > 0 else last_in_row(row)

        case "down":
            nr = (row + 1) % rows
            cand = nr * cols + col
            new_idx = cand if cand < total else last_in_row(nr)

        case "up":
            nr = (row - 1) % rows
            cand = nr * cols + col
            new_idx = cand if cand < total else last_in_row(nr)

        case _:
            return

    if 0 <= new_idx < total and new_idx != idx:
        items[new_idx].focus()
