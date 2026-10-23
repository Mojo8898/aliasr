"""Tests for command delivery, esp. the long-command path.

A command longer than the terminal's input buffer (~4 KB) can't be typed at the
prompt (it truncates) and can't be pasted into the live prompt without racing
the shell's line editor. inject() instead writes it to a temp file and injects a
tiny, race-free bootstrap: `source` to run it, or zsh `print -z` to load it into
the edit buffer for review; clipboard as a last resort. This holds in and out of
tmux (only a short bootstrap ever reaches the terminal).
"""

import os

from aliasr.core import inject as ij


def _long_cmd() -> str:
    return "echo " + "A" * (ij._INLINE_MAX + 500)  # safely over the inline limit


def test_short_command_is_typed_inline(monkeypatch):
    sent = {}
    monkeypatch.setattr(ij, "_tty_inject", lambda payload: sent.setdefault("tty", payload))
    ij.inject("echo hi", using_tmux=False, execute=True)
    assert sent["tty"] == "echo hi\n"


def test_long_execute_sources_a_tempfile(monkeypatch):
    delivered = {}
    monkeypatch.setattr(ij, "_tty_inject", lambda p, d=delivered: d.setdefault("payload", p))
    monkeypatch.setattr(ij, "_tmux_send_keys", lambda *a, **k: False)

    cmd = _long_cmd()
    ij.inject(cmd, using_tmux=True, execute=True, pane_index=None)

    payload = delivered["payload"]
    assert payload.startswith("source ") and "rm -f " in payload and payload.endswith("\n")
    assert len(payload) < 200  # a short bootstrap, not the 2.5 KB command
    path = payload.split("source ", 1)[1].split(";", 1)[0].strip().strip("'")
    assert oct(os.stat(path).st_mode & 0o777) == "0o600"
    assert open(path).read().startswith(cmd)
    os.unlink(path)


def test_long_review_zsh_uses_print_z(monkeypatch):
    """Under zsh, review mode loads the command into the edit buffer via print -z
    (no paste, no race) -- the bootstrap is run to populate the next prompt."""
    monkeypatch.setattr(ij, "_parent_shell", lambda: "zsh")
    delivered = {}
    monkeypatch.setattr(ij, "_tty_inject", lambda p, d=delivered: d.setdefault("payload", p))
    monkeypatch.setattr(ij, "_tmux_send_keys", lambda *a, **k: False)

    cmd = _long_cmd()
    ij.inject(cmd, using_tmux=False, execute=False)

    payload = delivered["payload"]
    assert payload.startswith("print -z -- ")
    assert payload.endswith("\n")  # bootstrap is run so print -z populates the buffer
    path = payload.split('"$(< ', 1)[1].split(")", 1)[0].strip().strip("'")
    assert open(path).read().startswith(cmd)
    os.unlink(path)


def test_long_review_non_zsh_copies_to_clipboard(monkeypatch):
    monkeypatch.setattr(ij, "_parent_shell", lambda: "bash")
    copied = {}
    monkeypatch.setattr(ij, "copy_to_clipboard", lambda c: copied.setdefault("cmd", c) or 0)
    monkeypatch.setattr(ij, "_tty_inject", lambda p: (_ for _ in ()).throw(AssertionError("typed!")))

    cmd = _long_cmd()
    ij.inject(cmd, using_tmux=False, execute=False)
    assert copied["cmd"] == cmd  # whole command, untruncated, on the clipboard


def test_long_review_non_zsh_falls_back_to_file(monkeypatch, capsys):
    monkeypatch.setattr(ij, "_parent_shell", lambda: "bash")
    monkeypatch.setattr(ij, "copy_to_clipboard", lambda _c: (_ for _ in ()).throw(RuntimeError("no clipboard")))
    monkeypatch.setattr(ij, "_tty_inject", lambda p: (_ for _ in ()).throw(AssertionError("typed!")))

    cmd = _long_cmd()
    ij.inject(cmd, using_tmux=False, execute=False)
    err = capsys.readouterr().err
    assert "saved to" in err
    path = err.split("saved to ", 1)[1].split(" ", 1)[0].strip()
    assert open(path).read().startswith(cmd)
    os.unlink(path)
