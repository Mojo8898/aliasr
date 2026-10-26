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
    assert mod.run_init(assume_yes=True) == 0

    zshrc = (home / ".zshrc").read_text(encoding="utf-8")
    tmux = (home / ".tmux.conf").read_text(encoding="utf-8")
    assert mod._BEGIN in zshrc and mod._END in zshrc
    assert "function a { aliasr" in zshrc
    assert 'bind K split-window "aliasr -e send -pp"' in tmux


def test_single_target_only_touches_that_file(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    mod.run_init(tmux=True, assume_yes=True)
    assert (home / ".tmux.conf").exists()
    assert not (home / ".zshrc").exists()


def test_idempotent_second_run_does_not_duplicate(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    mod.run_init(zsh=True, assume_yes=True)
    first = (home / ".zshrc").read_text(encoding="utf-8")
    mod.run_init(zsh=True, assume_yes=True)
    second = (home / ".zshrc").read_text(encoding="utf-8")
    assert first == second
    assert second.count(mod._BEGIN) == 1


def test_declining_prompt_leaves_file_untouched(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    monkeypatch.setattr(builtins, "input", lambda _p="": "n")
    mod.run_init(zsh=True)
    assert not (home / ".zshrc").exists()


def test_empty_answer_defaults_to_yes(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    monkeypatch.setattr(builtins, "input", lambda _p="": "")
    mod.run_init(tmux=True)
    assert (home / ".tmux.conf").exists()


def test_block_separated_from_existing_content(monkeypatch, tmp_path):
    home = _home(monkeypatch, tmp_path)
    zshrc = home / ".zshrc"
    zshrc.write_text("export FOO=1\n", encoding="utf-8")
    mod.run_init(zsh=True, assume_yes=True)
    text = zshrc.read_text(encoding="utf-8")
    assert text.startswith("export FOO=1\n")
    assert f"\n{mod._BEGIN}" in text  # blank line before the block
