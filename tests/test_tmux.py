"""Tests for the tmux bridge, focused on the libfaketime/skewrun workaround.

Under the DC-clock-skew workflow (``skewrun <ip> -- zsh`` / faketime), the whole
session preloads libfaketime and runs on a skewed clock. A tmux *client* spawned
from there inherits that preload and then hangs talking to the real-clock tmux
*server* until our 1s timeout fires -- a ~1s stall on every tmux call. ``_tmux``
therefore runs tmux with libfaketime stripped from the child environment.
"""

import subprocess

from aliasr.core import tmux


def test_deskewed_env_none_when_no_skew(monkeypatch):
    """No faketime present -> None, so the normal path inherits the env as-is."""
    monkeypatch.delenv("LD_PRELOAD", raising=False)
    monkeypatch.delenv("FAKETIME", raising=False)
    assert tmux._deskewed_env() is None


def test_deskewed_env_strips_faketime(monkeypatch):
    """libfaketime is removed from LD_PRELOAD and FAKETIME* vars are unset,
    while unrelated preloads and environment are preserved."""
    monkeypatch.setenv(
        "LD_PRELOAD", "/usr/$LIB/faketime/libfaketime.so.1:/other/lib.so"
    )
    monkeypatch.setenv("FAKETIME", "+1h")
    monkeypatch.setenv("FAKETIME_SHARED", "/faketime_sem_1 /faketime_shm_1")
    monkeypatch.setenv("UNRELATED", "keep-me")

    env = tmux._deskewed_env()

    assert env is not None
    assert "faketime" not in env["LD_PRELOAD"].lower()
    assert "/other/lib.so" in env["LD_PRELOAD"]
    assert "FAKETIME" not in env
    assert "FAKETIME_SHARED" not in env
    assert env["UNRELATED"] == "keep-me"


def test_deskewed_env_drops_empty_ld_preload(monkeypatch):
    """When libfaketime was the only preload, LD_PRELOAD is removed entirely
    (not left as an empty string, which the loader treats differently)."""
    monkeypatch.setenv("LD_PRELOAD", "/usr/lib/faketime/libfaketime.so.1")
    monkeypatch.delenv("FAKETIME", raising=False)

    env = tmux._deskewed_env()

    assert env is not None
    assert "LD_PRELOAD" not in env


def test_tmux_runs_child_with_deskewed_env(monkeypatch):
    """_tmux hands the de-skewed environment to the tmux subprocess so the
    client runs on the real clock and answers immediately."""
    monkeypatch.setenv("LD_PRELOAD", "/usr/lib/faketime/libfaketime.so.1")
    monkeypatch.setenv("FAKETIME", "+1h")

    captured = {}

    class _FakeCompleted:
        returncode = 0
        stdout = "1:5\n"

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env")
        captured["timeout"] = kwargs.get("timeout")
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", _fake_run)

    out = tmux._tmux("display-message", "-p", "#{pane_index}")

    assert out == "1:5"
    assert captured["cmd"][0] == "tmux"
    assert captured["timeout"] == 1.0
    assert captured["env"] is not None
    assert "FAKETIME" not in captured["env"]
    assert "LD_PRELOAD" not in captured["env"]


def test_tmux_inherits_env_when_no_skew(monkeypatch):
    """Without skew, env is left as None so the child inherits the parent's."""
    monkeypatch.delenv("LD_PRELOAD", raising=False)
    monkeypatch.delenv("FAKETIME", raising=False)

    captured = {}

    class _FakeCompleted:
        returncode = 0
        stdout = "2\n"

    def _fake_run(cmd, **kwargs):
        captured["env"] = kwargs.get("env")
        return _FakeCompleted()

    monkeypatch.setattr(subprocess, "run", _fake_run)

    assert tmux._tmux("display-message", "-p", "#{pane_index}") == "2"
    assert captured["env"] is None


# ---------- get_panes (base-index independence) ----------


def _panes(monkeypatch, listing: str | None):
    monkeypatch.setattr(tmux, "_tmux", lambda *a: listing)


def test_get_panes_base_index_1_active_first_wraps_to_last(monkeypatch):
    # pane-base-index 1: panes 1,2; active is the first -> previous wraps to 2
    # (the arithmetic bug produced the nonexistent pane "0" here).
    _panes(monkeypatch, "1:1\n2:0")
    assert tmux.get_panes() == ("1", "2")


def test_get_panes_base_index_1_active_second(monkeypatch):
    _panes(monkeypatch, "1:0\n2:1")
    assert tmux.get_panes() == ("2", "1")


def test_get_panes_base_index_0_active_first_wraps_to_last(monkeypatch):
    _panes(monkeypatch, "0:1\n1:0\n2:0")
    assert tmux.get_panes() == ("0", "2")


def test_get_panes_noncontiguous_after_close(monkeypatch):
    # Panes 1 and 3 (pane 2 was closed); predecessor of 1 wraps to 3.
    _panes(monkeypatch, "1:1\n3:0")
    assert tmux.get_panes() == ("1", "3")


def test_get_panes_single_pane(monkeypatch):
    _panes(monkeypatch, "1:1")
    assert tmux.get_panes() == ("1", "1")


def test_get_panes_no_tmux(monkeypatch):
    _panes(monkeypatch, None)
    assert tmux.get_panes() == (None, None)
