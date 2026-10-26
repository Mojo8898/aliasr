"""Tests for `aliasr list` flag dispatch.

-g lists only globals, -c only credentials; neither (or both) lists both.
"""

from aliasr.core import list as mod


def _spy(monkeypatch):
    calls = []
    monkeypatch.setattr(mod, "list_globals", lambda: calls.append("globals") or 0)
    monkeypatch.setattr(mod, "list_creds", lambda: calls.append("creds") or 0)
    monkeypatch.setattr(mod, "list_all", lambda: calls.append("all") or 0)
    return calls


def test_no_flags_lists_both(monkeypatch):
    calls = _spy(monkeypatch)
    assert mod.run_list() == 0
    assert calls == ["all"]


def test_globals_only(monkeypatch):
    calls = _spy(monkeypatch)
    mod.run_list(globals=True)
    assert calls == ["globals"]


def test_creds_only(monkeypatch):
    calls = _spy(monkeypatch)
    mod.run_list(creds=True)
    assert calls == ["creds"]


def test_both_flags_lists_both(monkeypatch):
    calls = _spy(monkeypatch)
    mod.run_list(globals=True, creds=True)
    assert calls == ["all"]
