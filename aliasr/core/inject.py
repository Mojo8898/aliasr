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
    elif outfile:
        return _write_to_file(cmd, outfile)
    elif using_tmux and pane_index and pane_index.isdigit():
        if _tmux_send_keys(pane_index, cmd, execute):
            return 0
    _tty_inject(cmd + ("\n" if execute else ""))
    return 0
