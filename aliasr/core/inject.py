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


def _enable_tiocsti() -> bool:
    """Offer to enable the legacy TIOCSTI sysctl, and apply it if accepted.

    Modern kernels ship it off because TIOCSTI lets a process inject keystrokes
    into a terminal; aliasr needs it to type the command at your prompt. On
    consent, applies a live ``sysctl -w`` plus a persistent drop-in in
    /etc/sysctl.d (idempotent — overwrites, never piling lines into sysctl.conf).
    Needs root for the privileged steps, or sudo. Returns True once enabled.

    Reached only after the TUI has exited, so we own a cooked terminal and can
    prompt. Enter accepts: aliasr is unusable without it, so the default is yes.
    """
    import shutil
    import subprocess

    try:
        answer = input(
            "aliasr requires TIOCSTI to inject commands, enable TIOCSTI now? [Y/n] "
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return False
    if answer in ("n", "no"):
        return False

    root = os.geteuid() == 0
    if root:
        sudo: list[str] = []
    elif shutil.which("sudo"):
        sudo = ["sudo"]
    else:
        print("aliasr: need root or sudo to enable TIOCSTI.", file=sys.stderr)
        return False

    drop_in = b"dev.tty.legacy_tiocsti = 1\n"
    path = "/etc/sysctl.d/aliasr.conf"
    try:
        subprocess.run(sudo + ["sysctl", "-w", "dev.tty.legacy_tiocsti=1"], check=True)
        if root:
            Path(path).write_bytes(drop_in)
        else:
            # tee under sudo so the redirect itself runs with privilege.
            subprocess.run(
                sudo + ["tee", path], input=drop_in, check=True, stdout=subprocess.DEVNULL
            )
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"aliasr: could not enable TIOCSTI: {exc}", file=sys.stderr)
        return False
    return True


def _tty_inject(payload: str, _allow_enable: bool = True) -> bool:
    """Inject characters directly into the current TTY.

    Returns True if the whole payload was pushed into the line buffer, False if
    it could not be (no controlling TTY, or TIOCSTI disabled). Callers rely on
    this to know whether the shell will actually run what we handed it.

    If TIOCSTI is disabled, offer to enable it and retry once — ``sysctl -w``
    takes effect immediately and system-wide, so a fresh /dev/tty picks it up.
    """
    import fcntl
    import termios

    try:
        tty = open("/dev/tty", "rb+", buffering=0)
    except OSError:
        return False
    disabled = False
    with tty:
        fd = tty.fileno()
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[3] &= ~(termios.ECHO | termios.ICANON)
        try:
            termios.tcsetattr(fd, termios.TCSANOW, new)
            for byte in payload.encode("utf-8"):
                fcntl.ioctl(fd, termios.TIOCSTI, bytes([byte]))
        except OSError:
            disabled = True
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
    if disabled:
        # Terminal is restored (finally ran); safe to prompt now, then retry once.
        if _allow_enable and _enable_tiocsti():
            return _tty_inject(payload, _allow_enable=False)
        return False
    return True


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


# The terminal input buffer -- the kernel tty line-discipline queue
# (N_TTY_BUF_SIZE) -- holds this many bytes before it silently drops whatever
# overflows, truncating a longer command mid-flight. Measured identical (4095) on
# modern Linux, in and out of tmux and over ssh. A command we type at the prompt
# -- plus the trailing newline when we press Enter for it -- must fit under this;
# anything larger we never type (pasting the whole command into the live line
# editor races it and doubles/garbles the echo), we copy it to the clipboard.
_TTY_LIMIT = 4095


def _write_cmd_tempfile(cmd: str) -> str:
    """Write ``cmd`` to a private (0600) temp file and return its path."""
    import tempfile

    fd, path = tempfile.mkstemp(prefix="aliasr-run-", suffix=".sh")
    try:
        os.write(fd, (cmd if cmd.endswith("\n") else cmd + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    return path


def _deliver_inline(cmd: str, using_tmux: bool, execute: bool, pane_index: str | None) -> bool:
    """Type a (short) command at the prompt, or send it to a target tmux pane.

    Returns True if the command was delivered, False if it could not be.
    """
    if using_tmux and pane_index and pane_index.isdigit():
        if _tmux_send_keys(pane_index, cmd, execute):
            return True
    return _tty_inject(cmd + ("\n" if execute else ""))


def _fallback_clipboard(cmd: str) -> int:
    """Hand off a command too long to type at the prompt.

    A command over the tty input buffer can't be typed (it truncates) and can't
    be pasted into the live prompt without racing the line editor, so we don't try
    either: we copy the whole command to the clipboard for the user to paste --
    to run or edit. This behaves the same in and out of tmux/ssh and for both
    execute and review; we can't press Enter for them, but the command is intact.

    If no clipboard backend is reachable (and OSC 52 also fails), we save the
    command to a private (0600) file and tell the user how to run it, so a long
    command is never silently lost.
    """
    try:
        copy_to_clipboard(cmd)
        print(
            f"Command length longer than {_TTY_LIMIT} byte cap. Copied to clipboard!",
            file=sys.stderr,
        )
    except Exception:
        path = _write_cmd_tempfile(cmd)
        print(
            "aliasr: command too long to type and no clipboard backend available; "
            f"saved to {path} — run it with: . {path}",
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
    # What we'd type is the command plus a trailing newline when we execute it; if
    # that would overflow the tty input buffer, hand off via the clipboard rather
    # than type a command the kernel would truncate mid-flight.
    if len(cmd.encode("utf-8")) + (1 if execute else 0) > _TTY_LIMIT:
        return _fallback_clipboard(cmd)
    return 0 if _deliver_inline(cmd, using_tmux, execute, pane_index) else 1
