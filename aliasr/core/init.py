"""`aliasr init` -- append aliasr's shell/tmux integration to the user's config.

Each target's snippet ships as a data file and is appended inside a marked
block so a re-run is idempotent (an existing block is detected and skipped,
never duplicated). Dotfiles are the user's own, so each append is confirmed
unless --yes is passed.
"""

import os
from pathlib import Path

# The installed package dir -- mirrors core/config.py's PKG_DIR.
PKG_DIR: Path = Path(__file__).parent.parent

_BEGIN = "# >>> aliasr >>>"
_END = "# <<< aliasr <<<"

# target -> (destination dotfile, shipped snippet)
_TARGETS: dict[str, tuple[str, str]] = {
    "zsh": ("~/.zshrc", "zsh.sh"),
    "tmux": ("~/.tmux.conf", "tmux.conf"),
}


def _snippet(name: str) -> str:
    return (PKG_DIR / "data" / "init" / name).read_text(encoding="utf-8")


def _marked_block(body: str) -> str:
    return f"{_BEGIN}\n{body.strip(chr(10))}\n{_END}\n"


def _append(path: Path, body: str) -> str:
    """Append a marked block to ``path``. Returns 'exists' or 'added'.

    Scoping is the -z/-t flags' job, so this doesn't prompt -- it just appends,
    skipping only when the file already holds an aliasr block (idempotent).
    """
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if _BEGIN in existing:
        return "exists"
    # Separate the block from any prior content with a blank line.
    sep = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(sep + _marked_block(body))
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
