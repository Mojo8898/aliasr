"""Unit tests for assembling a stored cheat into an executable command."""

import os
import subprocess

from aliasr.core.assemble import assemble, faketime_guard, split_commands

SEP = r"""printf '\n=== %s ===\n' "$1" """.strip()


def test_split_commands_newlines_and_continuation():
    assert split_commands("a\nb\nc") == ["a", "b", "c"]
    # a trailing "\" continues onto the next line (one logical command)
    assert split_commands("for x in a; do \\\n echo $x; \\\ndone\nnext") == [
        "for x in a; do \\\n echo $x; \\\ndone",
        "next",
    ]
    assert split_commands("only") == ["only"]
    # blank lines are ignored
    assert split_commands("a\n\n\nb") == ["a", "b"]


def test_assemble_single_command_unchanged():
    assert assemble("just one <ip>", SEP) == "just one <ip>"


def test_assemble_multi_has_separator_and_commands():
    out = assemble("echo a\necho b", SEP)
    assert out.startswith("s(){ ")
    assert "s 'echo a'; echo a" in out
    assert "s 'echo b'; echo b" in out


def test_assembled_command_runs_in_bash():
    """The assembled command must execute: banner before each step, every step
    runs, and a command containing single quotes survives the quoting."""
    out = assemble("echo alpha\necho with 'quoted' word\necho omega", SEP)
    r = subprocess.run(["bash", "-c", out], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "=== echo alpha ===" in r.stdout
    assert "=== echo with 'quoted' word ===" in r.stdout
    assert "alpha" in r.stdout and "omega" in r.stdout
    assert "with quoted word" in r.stdout


def test_split_commands_operator_continuation():
    # a line ending in a pipe / && / || continues onto the next line
    assert split_commands("cat x |\ngrep y\necho done") == ["cat x |\ngrep y", "echo done"]
    assert split_commands("a &&\nb") == ["a &&\nb"]


def test_assemble_wrap_applies_per_command_not_to_separator():
    out = assemble("echo a\necho b", SEP, wrap=lambda c: f"proxychains -q {c}")
    assert out.startswith("s(){ ")                 # separator NOT prefixed
    assert "s 'echo a'; proxychains -q echo a" in out
    assert "s 'echo b'; proxychains -q echo b" in out


def test_assemble_wrap_single_command():
    assert assemble("echo a", SEP, wrap=lambda c: f"sudo {c}") == "sudo echo a"


def test_prefixed_multi_command_runs_in_bash():
    """Regression: a prefix on an assembled multi-command cheat must stay valid
    shell (was: 'proxychains s(){...}' -> syntax error)."""
    import subprocess
    out = assemble("echo a\necho b", SEP, wrap=lambda c: f"env {c}")  # 'env X' runs X
    r = subprocess.run(["bash", "-c", out], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "a" in r.stdout and "b" in r.stdout


# ---------- faketime guard ----------


def test_faketime_guard_structure():
    g = faketime_guard("nxc smb 10.0.0.1 -k", "10.0.0.1")
    assert g.startswith('if [ -n "$FAKETIME" ]; then nxc smb 10.0.0.1 -k; else ')
    assert "skewrun 10.0.0.1 -- sh -c " in g  # unskewed branch runs under skewrun
    assert g.endswith("; fi")


def test_faketime_guard_as_wrap_keeps_banner_clean():
    """Used as assemble's wrap, the guard wraps the executed command but the
    `s '<label>'` banner still announces the bare command (no skewrun)."""
    out = assemble("echo a\necho b", SEP, wrap=lambda c: faketime_guard(c, "1.2.3.4"))
    assert "s 'echo a'" in out and "s 'echo b'" in out  # clean labels
    assert "s 'skewrun" not in out  # no banner announces the wrapper
    assert 'if [ -n "$FAKETIME" ]; then echo a; else skewrun 1.2.3.4 -- sh -c ' in out


def test_faketime_guard_runs_bare_when_already_skewed():
    """$FAKETIME set (already in a skewrun session) -> command runs as-is and
    skewrun is never invoked (PATH has no skewrun, yet it still succeeds)."""
    # skewrun isn't installed here, so if the else-branch ran this would fail;
    # it succeeds only because $FAKETIME routes to the bare command.
    g = faketime_guard("echo hi", "1.2.3.4")
    r = subprocess.run(["bash", "-c", g], capture_output=True, text=True,
                       env={**os.environ, "FAKETIME": "+1s"})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "hi"


def test_faketime_guard_invokes_skewrun_when_not_skewed(tmp_path):
    """$FAKETIME unset -> the command is handed to `skewrun <target> -- sh -c`."""
    stub = tmp_path / "skewrun"
    stub.write_text('#!/bin/sh\necho "SKEW:$1"\nshift 2\nexec "$@"\n')  # $1=target; drop target + '--'
    stub.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k != "FAKETIME"}
    env["PATH"] = f"{tmp_path}:{env['PATH']}"

    g = faketime_guard("echo deep", "10.9.8.7")
    r = subprocess.run(["bash", "-c", g], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "SKEW:10.9.8.7" in r.stdout  # skewrun got the target
    assert "deep" in r.stdout           # and the wrapped command still ran
