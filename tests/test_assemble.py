"""Unit tests for assembling a stored cheat into an executable command."""

from aliasr.core.assemble import assemble, split_commands


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


def test_split_commands_operator_continuation():
    # a line ending in a pipe / && / || continues onto the next line
    assert split_commands("cat x |\ngrep y\necho done") == ["cat x |\ngrep y", "echo done"]
    assert split_commands("a &&\nb") == ["a &&\nb"]


# ---------- single command ----------


def test_assemble_single_command_unchanged():
    assert assemble("just one <ip>") == "just one <ip>"


def test_assemble_single_command_wrapped():
    assert assemble("echo a", wrap=lambda c: f"sudo {c}") == "sudo echo a"


# ---------- multi-line arun chain ----------


def test_assemble_multi_wraps_each_in_arun():
    out = assemble("echo a\necho b")
    assert out == "arun echo a ; \\\narun echo b"
    assert "arun echo a" in out and "arun echo b" in out
    assert "s(){" not in out  # old separator machinery is gone


def test_assemble_multi_is_unquoted_passthrough():
    """A step's trailing `&& export ...` is emitted verbatim after `arun`, so the
    parent shell parses it and the env change persists into later steps."""
    out = assemble("getTGT.py dom/user && export KRB5CCNAME=$(pwd)/user.ccache\nbloodyAD -k")
    assert "arun getTGT.py dom/user && export KRB5CCNAME=$(pwd)/user.ccache" in out
    assert "arun bloodyAD -k" in out


def test_assemble_multi_wrap_applies_inside_arun():
    out = assemble("echo a\necho b", wrap=lambda c: f"proxychains -q {c}")
    assert "arun proxychains -q echo a" in out
    assert "arun proxychains -q echo b" in out


# ---------- skew target (faketime) ----------


def test_assemble_skew_target_exports_ar_skew():
    out = assemble("echo a\necho b", skew_target="10.0.0.1")
    assert out.startswith("export AR_SKEW=10.0.0.1 ; \\\n")
    assert "arun echo a" in out and "arun echo b" in out


def test_assemble_skew_target_is_quoted():
    out = assemble("echo a\necho b", skew_target="a b")
    assert "export AR_SKEW='a b'" in out


def test_assemble_no_skew_has_no_ar_skew():
    assert "AR_SKEW" not in assemble("echo a\necho b")


def test_assemble_skew_ignored_for_single_command():
    # single command never enters the arun chain, so AR_SKEW is irrelevant
    assert assemble("echo a", skew_target="10.0.0.1") == "echo a"


# ---------- #target/local: emitted bare ----------


def test_assemble_local_multi_is_bare():
    out = assemble("echo a\necho b", local=True)
    assert out == "echo a ; \\\necho b"
    assert "arun" not in out
    assert "AR_SKEW" not in out


def test_assemble_local_ignores_skew_target():
    out = assemble("echo a\necho b", local=True, skew_target="10.0.0.1")
    assert "arun" not in out and "AR_SKEW" not in out


def test_assemble_local_single_command():
    assert assemble("echo a", local=True) == "echo a"
