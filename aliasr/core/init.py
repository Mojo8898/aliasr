"""`aliasr init` -- append aliasr's shell/tmux integration to the user's config.

Each target's snippet ships as a data file and is appended inside a marked
block so a re-run is idempotent (an existing block is detected and skipped,
never duplicated). Dotfiles are the user's own, so each append is confirmed
unless --yes is passed.
"""

import os
import sys
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


def _append(path: Path, body: str, assume_yes: bool) -> str:
    """Append a marked block to ``path``. Returns 'exists', 'added', or 'declined'."""
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if _BEGIN in existing:
        return "exists"
    if not assume_yes:
        try:
            answer = input(f"Append aliasr config to {path}? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            return "declined"
        if answer in ("n", "no"):
            return "declined"
    # Separate the block from any prior content with a blank line.
    sep = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(sep + _marked_block(body))
    return "added"


def run_init(target: str | None = None, assume_yes: bool = False) -> int:
    """Append integration snippets for the given target (zsh/tmux), or both."""
    names = ["zsh", "tmux"] if target in (None, "all") else [target]
    added = False
    for name in names:
        dest, snippet = _TARGETS[name]
        path = Path(os.path.expanduser(dest))
        status = _append(path, _snippet(snippet), assume_yes)
        if status == "exists":
            print(f"{path}: already configured, skipping.")
        elif status == "added":
            print(f"{path}: added aliasr block.")
            added = True
        else:
            print(f"{path}: skipped.")
    if added:
        print("\nStart a new shell (or `exec zsh`) / reload tmux to apply.")
    return 0
