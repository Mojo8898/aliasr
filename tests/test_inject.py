"""Tests for command delivery, esp. the long-command path.

A command that would overflow the terminal's input buffer (N_TTY_BUF_SIZE, 4095
bytes on modern Linux) can't be typed at the prompt -- the kernel silently drops
the overflow -- and can't be pasted into the live prompt without racing the
shell's line editor. So inject() types a command only while it fits (counting the
Enter newline when it executes it); anything larger is copied to the clipboard for
the user to paste, with a saved 0600 file as the last resort when no clipboard
backend exists. The cap is the same in and out of tmux/ssh.
"""

import os

from aliasr.core import inject as ij


def _long_cmd() -> str:
    return "echo " + "A" * (ij._TTY_LIMIT + 500)  # safely over the inline limit


def _no_clipboard(_c):
    raise AssertionError("copied to clipboard!")


def _no_tty(_p):
    raise AssertionError("typed into the tty!")


def test_short_command_is_typed_inline(monkeypatch):
    sent = {}
    monkeypatch.setattr(ij, "_tty_inject", lambda payload: sent.setdefault("tty", payload))
    ij.inject("echo hi", using_tmux=False, execute=True)
    assert sent["tty"] == "echo hi\n"


def test_long_execute_copies_whole_command_to_clipboard(monkeypatch):
    copied = {}
    monkeypatch.setattr(ij, "copy_to_clipboard", lambda c: copied.setdefault("cmd", c) or 0)
    monkeypatch.setattr(ij, "_tty_inject", _no_tty)
    monkeypatch.setattr(ij, "_tmux_send_keys", lambda *a, **k: False)

    cmd = _long_cmd()
    rc = ij.inject(cmd, using_tmux=True, execute=True, pane_index=None)

    assert rc == 0
    assert copied["cmd"] == cmd  # whole command, untruncated, on the clipboard


def test_long_review_copies_whole_command_to_clipboard(monkeypatch):
    copied = {}
    monkeypatch.setattr(ij, "copy_to_clipboard", lambda c: copied.setdefault("cmd", c) or 0)
    monkeypatch.setattr(ij, "_tty_inject", _no_tty)

    cmd = _long_cmd()
    ij.inject(cmd, using_tmux=False, execute=False)
    assert copied["cmd"] == cmd


def test_long_falls_back_to_0600_file_without_clipboard(monkeypatch, capsys):
    monkeypatch.setattr(ij, "copy_to_clipboard", lambda _c: (_ for _ in ()).throw(RuntimeError("no clipboard")))
    monkeypatch.setattr(ij, "_tty_inject", _no_tty)

    cmd = _long_cmd()
    rc = ij.inject(cmd, using_tmux=False, execute=False)

    assert rc == 0
    err = capsys.readouterr().err
    assert "saved to" in err
    path = err.split("saved to ", 1)[1].split(" ", 1)[0].strip()
    assert oct(os.stat(path).st_mode & 0o777) == "0o600"
    assert open(path).read().startswith(cmd)
    os.unlink(path)


def test_execute_boundary_fits_with_the_enter_newline(monkeypatch):
    """A command whose length + the Enter newline is exactly the tty limit is
    still typed -- the newline must be counted, or Enter would be the byte dropped."""
    sent = {}
    monkeypatch.setattr(ij, "_tty_inject", lambda p: sent.setdefault("p", p) or True)
    monkeypatch.setattr(ij, "copy_to_clipboard", _no_clipboard)

    cmd = "A" * (ij._TTY_LIMIT - 1)  # cmd + "\n" == _TTY_LIMIT
    ij.inject(cmd, execute=True)
    assert sent["p"] == cmd + "\n"


def test_execute_one_byte_over_goes_to_clipboard(monkeypatch):
    copied = {}
    monkeypatch.setattr(ij, "copy_to_clipboard", lambda c: copied.setdefault("c", c) or 0)
    monkeypatch.setattr(ij, "_tty_inject", _no_tty)

    cmd = "A" * ij._TTY_LIMIT  # cmd + "\n" == _TTY_LIMIT + 1 -> overflows
    ij.inject(cmd, execute=True)
    assert copied["c"] == cmd


def test_review_boundary_exactly_fills_the_buffer(monkeypatch):
    """Review types no newline, so the command itself may fill the buffer exactly."""
    sent = {}
    monkeypatch.setattr(ij, "_tty_inject", lambda p: sent.setdefault("p", p) or True)
    monkeypatch.setattr(ij, "copy_to_clipboard", _no_clipboard)

    cmd = "A" * ij._TTY_LIMIT
    ij.inject(cmd, execute=False)
    assert sent["p"] == cmd


def test_review_one_byte_over_goes_to_clipboard(monkeypatch):
    copied = {}
    monkeypatch.setattr(ij, "copy_to_clipboard", lambda c: copied.setdefault("c", c) or 0)
    monkeypatch.setattr(ij, "_tty_inject", _no_tty)

    cmd = "A" * (ij._TTY_LIMIT + 1)
    ij.inject(cmd, execute=False)
    assert copied["c"] == cmd
