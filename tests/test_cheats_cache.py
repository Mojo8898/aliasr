"""Cache-invalidation coverage for aliasr.core.cheats.

Regression guard for the stale-pickle bug: ``load_cheats()`` used to reuse the
cache whenever the file existed, so edits/additions/deletions to the markdown
were masked until the cache was cleared by hand. These tests point the module
at a temp corpus + temp cache and assert the cache is rebuilt on any change.
"""

from pathlib import Path

import pytest

from aliasr.core import cheats


@pytest.fixture
def corpus(tmp_path, monkeypatch) -> Path:
    """An isolated cheat dir + cache, wired into the cheats module.

    Redirects the cache under ``XDG_CACHE_HOME`` (honored by ``_cache_path``)
    and points ``CHEAT_PATHS`` at a throwaway directory so the real bundled
    cheats and the user's real cache are untouched.
    """
    cheat_dir = tmp_path / "cheats"
    cheat_dir.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(cheats, "CHEAT_PATHS", (cheat_dir,))
    monkeypatch.setattr(cheats, "CHEATS_EXCLUDE", ())
    return cheat_dir


def _write(path: Path, title: str, cmd: str) -> None:
    path.write_text(f"# {title}\n\n## {title}\n```\n{cmd}\n```\n")


def _cmds() -> set[str]:
    return {c.cmd for c in cheats.get_loaded_cheats()}


def test_edit_invalidates_cache(corpus):
    """Editing a cheat body is reflected on the next load (the reported bug)."""
    f = corpus / "sample.md"
    _write(f, "sample", "old-command")
    cheats.load_cheats()
    assert "old-command" in _cmds()

    # Rewrite with new content; bump mtime so the signature is guaranteed to
    # differ even on coarse-resolution clocks.
    _write(f, "sample", "new-command")
    import os

    st = f.stat()
    os.utime(f, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))

    cheats.load_cheats()
    cmds = _cmds()
    assert "new-command" in cmds
    assert "old-command" not in cmds


def test_added_file_invalidates_cache(corpus):
    """A newly added cheat file shows up without a manual cache clear."""
    _write(corpus / "a.md", "a", "cmd-a")
    cheats.load_cheats()
    assert _cmds() == {"cmd-a"}

    _write(corpus / "b.md", "b", "cmd-b")
    cheats.load_cheats()
    assert _cmds() == {"cmd-a", "cmd-b"}


def test_deleted_file_invalidates_cache(corpus):
    """Deleting a cheat file drops it from the corpus on the next load."""
    _write(corpus / "a.md", "a", "cmd-a")
    _write(corpus / "b.md", "b", "cmd-b")
    cheats.load_cheats()
    assert _cmds() == {"cmd-a", "cmd-b"}

    (corpus / "b.md").unlink()
    cheats.load_cheats()
    assert _cmds() == {"cmd-a"}


def test_unchanged_corpus_reuses_cache(corpus, monkeypatch):
    """Steady state: an unchanged corpus hits the cache and does NOT reparse."""
    _write(corpus / "a.md", "a", "cmd-a")
    cheats.load_cheats()  # primes the cache

    def _boom(*_args, **_kwargs):
        raise AssertionError("cache hit must not reparse markdown")

    monkeypatch.setattr(cheats, "_build_from_files", _boom)
    cheats.load_cheats()  # must be served from cache, no rebuild
    assert _cmds() == {"cmd-a"}


def test_corrupt_cache_rebuilds(corpus):
    """A garbage cache file is treated as a miss and rebuilt, not a crash."""
    _write(corpus / "a.md", "a", "cmd-a")
    cheats.load_cheats()

    cheats._cache_path().write_bytes(b"not a pickle")
    cheats.load_cheats()
    assert _cmds() == {"cmd-a"}
