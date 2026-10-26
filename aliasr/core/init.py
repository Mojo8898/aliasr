"""`aliasr init` -- append aliasr's shell/tmux integration to the user's config.

Each target's snippet ships as a data file headed by a ``# aliasr`` tag line
and is appended as-is. A re-run is idempotent: if the file already contains
that tag line, the append is skipped. Scoping is the -z/-t flags' job, so this
never prompts.
"""

import os
from pathlib import Path

# The installed package dir -- mirrors core/config.py's PKG_DIR.
PKG_DIR: Path = Path(__file__).parent.parent

# The tag line each snippet starts with; also the idempotency marker.
_TAG = "# aliasr"

# target -> (destination dotfile, shipped snippet)
_TARGETS: dict[str, tuple[str, str]] = {
    "zsh": ("~/.zshrc", "zsh.sh"),
    "tmux": ("~/.tmux.conf", "tmux.conf"),
}


def _snippet(name: str) -> str:
    return (PKG_DIR / "data" / "init" / name).read_text(encoding="utf-8")


def _append(path: Path, body: str) -> str:
    """Append the snippet to ``path``. Returns 'exists' or 'added'.

    Skips when the file already has the ``# aliasr`` tag line (idempotent).
    """
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if _TAG in existing.splitlines():
        return "exists"
    # Separate the block from any prior content with a blank line.
    sep = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(sep + body)
    return "added"


def run_init(zsh: bool = False, tmux: bool = False) -> int:
    """Append integration snippets. With neither flag (or both), set up both."""
    if zsh and not tmux:
        names = ["zsh"]
    elif tmux and not zsh:
        names = ["tmux"]
    else:
        names = ["zsh", "tmux"]
    added = False
    for name in names:
        dest, snippet = _TARGETS[name]
        path = Path(os.path.expanduser(dest))
        status = _append(path, _snippet(snippet))
        if status == "exists":
            print(f"{path}: already configured, skipping.")
        else:
            print(f"{path}: added aliasr block.")
            added = True
    if added:
        print("\nStart a new shell (or `exec zsh`) / reload tmux to apply.")
    return 0
