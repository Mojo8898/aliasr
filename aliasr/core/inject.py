import os
import sys
from pathlib import Path


# ---------- Internal ----------


def _write_to_file(cmd: str, outfile: str) -> int:
    """Write command to a file, or stdout if outfile == '-'."""
    text = cmd if cmd.endswith("\n") else cmd + "\n"
    if outfile == "-":
        sys.stdout.write(text)
    else:
        path = Path(os.path.expanduser(outfile))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return 0


def _tmux_send_keys(pane: str, cmd: str, execute: bool) -> bool:
    """Send keys to a tmux pane. Returns True if attempted."""
    try:
        from aliasr.core.tmux import get_current_pane

        if pane != get_current_pane():
            if execute:
                from aliasr.core.tmux import send_cmd

                send_cmd(cmd, pane)
            else:
                from aliasr.core.tmux import send_and_select

                send_and_select(cmd, pane)
            return True
    except Exception:
        return False


def _tty_inject(payload: str) -> None:
    """Inject characters directly into the current TTY."""
    import fcntl
    import termios

    with open("/dev/tty", "rb+", buffering=0) as tty:
        fd = tty.fileno()
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] &= ~(termios.ECHO | termios.ICANON)
        try:
            termios.tcsetattr(fd, termios.TCSANOW, new)
            for ch in payload:
                fcntl.ioctl(fd, termios.TIOCSTI, ch)
        except OSError:
            print("""========== OSError ============
aliasr needs TIOCSTI enabled for running
Please run the following commands as root to fix this issue on the current session:
sysctl -w dev.tty.legacy_tiocsti=1

If you want this workaround to survive a reboot,
add the following configuration to sysctl.conf file and reboot:
echo "dev.tty.legacy_tiocsti=1" >> /etc/sysctl.conf

More details: https://github.com/Orange-Cyberdefense/arsenal/issues/77
""")
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ---------- Public API ----------


def _osc52_copy(text: str) -> bool:
    """Copy via the OSC 52 terminal escape, written to the controlling TTY.

    Backend-independent: works over SSH and inside tmux (with clipboard
    passthrough) without xclip/xsel/wl-copy or clip.exe. Returns True if the
    sequence was written. Mirrors ``_tty_inject`` by talking to /dev/tty
    directly, so it also works while the Textual TUI owns stdout.
    """
    import base64

    b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
    seq = f"\033]52;c;{b64}\a"
    if os.environ.get("TMUX"):
        # Wrap so tmux forwards the sequence to the outer terminal.
        seq = f"\033Ptmux;\033{seq}\033\\"
    try:
        with open("/dev/tty", "w") as tty:
            tty.write(seq)
            tty.flush()
        return True
    except OSError:
        return False


def copy_to_clipboard(cmd: str) -> int:
    """Copy command to clipboard using best available backend.

    Falls back to OSC 52 when no native clipboard tool is reachable (common on
    headless/WSL/SSH setups), so copying works without xclip/xsel/wl-copy.
    """
    import shutil
    import pyperclip

    if os.environ.get("WAYLAND_DISPLAY") and shutil.which("wl-copy"):
        pyperclip.set_clipboard("wl-clipboard")
    elif shutil.which("xclip"):
        pyperclip.set_clipboard("xclip")
    elif shutil.which("xsel"):
        pyperclip.set_clipboard("xsel")

    try:
        pyperclip.copy(cmd)
    except Exception:
        # pyperclip found no working backend (it may even raise
        # FileNotFoundError probing clip.exe on WSL) — try OSC 52.
        if not _osc52_copy(cmd):
            raise
    return 0


# A command longer than this is not typed into the shell: the terminal input
# buffer (the kernel tty line-discipline queue, ~4 KB and kernel-dependent)
# silently drops whatever overflows it, truncating long commands mid-flight.
# Kept well under that floor so it holds in and out of tmux, on any box.
_INLINE_MAX = 2048


def _write_cmd_tempfile(cmd: str) -> str:
    """Write ``cmd`` to a private (0600) temp file and return its path."""
    import tempfile

    fd, path = tempfile.mkstemp(prefix="aliasr-run-", suffix=".sh")
    try:
        os.write(fd, (cmd if cmd.endswith("\n") else cmd + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    return path


def _deliver_inline(cmd: str, using_tmux: bool, execute: bool, pane_index: str | None) -> None:
    """Type a (short) command at the prompt, or send it to a target tmux pane."""
    if using_tmux and pane_index and pane_index.isdigit():
        if _tmux_send_keys(pane_index, cmd, execute):
            return
    _tty_inject(cmd + ("\n" if execute else ""))


_KNOWN_SHELLS = ("zsh", "bash", "fish", "dash", "ksh", "sh")


def _parent_shell() -> str:
    """Name of the interactive shell aliasr will hand the command back to.

    Prefer aliasr's parent process when it is itself a shell; otherwise (e.g.
    launched via ``uv run``/a wrapper, so the parent is not a shell) fall back
    to ``$SHELL``.
    """
    try:
        with open(f"/proc/{os.getppid()}/comm", encoding="utf-8") as f:
            comm = f.read().strip().lstrip("-")
        if any(s in comm for s in _KNOWN_SHELLS):
            return comm
    except OSError:
        pass
    return os.path.basename(os.environ.get("SHELL", "")).strip()


def _inject_long(cmd: str, using_tmux: bool, execute: bool, pane_index: str | None) -> int:
    """Deliver a command too long to type at the prompt (in or out of tmux).

    A long command can't be pushed through the terminal input buffer (it is
    truncated at ~4 KB), and pasting it into the live prompt races the shell's
    line editor (causing a doubled/garbled echo). So we never deliver the whole
    command that way: we write it to a temp file and inject only a tiny,
    race-free bootstrap that the shell runs itself.

    * execute -> ``source <file>`` runs it in the current shell (exports
      persist; the announce banners still show each step).
    * review (zsh) -> ``print -z`` loads the full command into zsh's next edit
      buffer, so it appears at the prompt ready to review/edit/run -- no paste.
    * review (other shells) -> copy to the clipboard (no portable way to preload
      the line editor), falling back to a saved file.
    """
    import shlex

    path = _write_cmd_tempfile(cmd)
    q = shlex.quote(path)
    shell = _parent_shell()

    if execute:
        _deliver_inline(f"source {q}; rm -f {q}", using_tmux, True, pane_index)
        return 0

    if "zsh" in shell:
        # The bootstrap runs (hence execute=True); print -z then pops the full
        # command into the next prompt's editable buffer.
        _deliver_inline(f'print -z -- "$(< {q})"; rm -f {q}', using_tmux, True, pane_index)
        return 0

    try:
        copy_to_clipboard(cmd)
        print(
            f"aliasr: command is {len(cmd)} bytes, over the terminal's input limit; "
            "copied to clipboard — paste it to run or edit.",
            file=sys.stderr,
        )
        os.unlink(path)
    except Exception:
        print(
            "aliasr: command too long to type and no clipboard backend available; "
            f"saved to {path} — run it with: source {path}",
            file=sys.stderr,
        )
    return 0


def inject(
    cmd: str = "",
    copy: bool = False,
    outfile: str | None = None,
    using_tmux: bool = False,
    execute: bool = False,
    pane_index: str | None = None,
) -> int:
    """Build the final command string and inject"""
    if copy:
        return copy_to_clipboard(cmd)
    if outfile:
        return _write_to_file(cmd, outfile)
    if len(cmd) > _INLINE_MAX:
        return _inject_long(cmd, using_tmux, execute, pane_index)
    _deliver_inline(cmd, using_tmux, execute, pane_index)
    return 0
