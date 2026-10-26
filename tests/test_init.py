"""Tests for `aliasr init` -- appending integration blocks to dotfiles.

Each target's snippet is appended inside a marked block; a re-run must detect
the existing block and never duplicate it. Dotfiles are pointed at a temp HOME.
"""

import builtins

from aliasr.core import init as mod


def _home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_appends_both_blocks(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    assert mod.run_init() == 0

    zshrc = (home / ".zshrc").read_text(encoding="utf-8")
    tmux = (home / ".tmux.conf").read_text(encoding="utf-8")
    assert mod._BEGIN in zshrc and mod._END in zshrc
    assert "function a { aliasr" in zshrc
    assert 'bind K split-window "aliasr -e send -pp"' in tmux


def test_single_target_only_touches_that_file(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    mod.run_init(tmux=True)
    assert (home / ".tmux.conf").exists()
    assert not (home / ".zshrc").exists()


def test_idempotent_second_run_does_not_duplicate(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    mod.run_init(zsh=True)
    first = (home / ".zshrc").read_text(encoding="utf-8")
    mod.run_init(zsh=True)
    second = (home / ".zshrc").read_text(encoding="utf-8")
    assert first == second
    assert second.count(mod._BEGIN) == 1


def test_appends_without_prompting(monkeypatch, tmp_path):
    """The -z/-t flags are the scope control, so init never prompts."""
    home = _home(monkeypatch, tmp_path)

    def _boom(*_a, **_k):
        raise AssertionError("init must not prompt")

    monkeypatch.setattr(builtins, "input", _boom)
    mod.run_init(zsh=True)
    assert (home / ".zshrc").exists()


def test_block_separated_from_existing_content(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    zshrc = home / ".zshrc"
    zshrc.write_text("export FOO=1\n", encoding="utf-8")
    mod.run_init(zsh=True)
    text = zshrc.read_text(encoding="utf-8")
    assert text.startswith("export FOO=1\n")
    assert f"\n{mod._BEGIN}" in text  # blank line before the block
