"""Unit tests for assembling a stored cheat into an executable command."""

import pathlib
import re

import aliasr
from aliasr.core.assemble import assemble, split_commands
from aliasr.core.cheats import _parse_markdown


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
    assert split_commands("cat x |\ngrep y\necho done") == [
        "cat x |\ngrep y",
        "echo done",
    ]
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
    out = assemble(
        "getTGT.py dom/user && export KRB5CCNAME=$(pwd)/user.ccache\nbloodyAD -k"
    )
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


def test_assemble_single_command_skew_scopes_ar_skew_to_one_arun():
    # a lone #faketime command (e.g. getTGT) still needs skew: AR_SKEW is scoped
    # to the single arun call rather than exported, and nothing leaks to the parent
    out = assemble("getTGT.py dom/user", skew_target="10.0.0.1")
    assert out == "AR_SKEW=10.0.0.1 arun getTGT.py dom/user"
    assert not out.startswith("export ")


def test_assemble_single_command_skew_is_quoted():
    out = assemble("getTGT.py dom/user", skew_target="a b")
    assert out == "AR_SKEW='a b' arun getTGT.py dom/user"


def test_assemble_single_command_skew_wrap_applies_inside_arun():
    out = assemble(
        "getTGT.py dom/user",
        skew_target="10.0.0.1",
        wrap=lambda c: f"proxychains -q {c}",
    )
    assert out == "AR_SKEW=10.0.0.1 arun proxychains -q getTGT.py dom/user"


def test_assemble_single_command_no_skew_stays_bare():
    assert assemble("getTGT.py dom/user") == "getTGT.py dom/user"


def test_assemble_single_local_faketime_stays_bare():
    # a #target/local cheat emits bare even with a skew target (foreign host)
    assert assemble("whoami", local=True, skew_target="10.0.0.1") == "whoami"


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


# ---------- backgrounded steps (trailing &) ----------


def test_assemble_backgrounded_step_not_followed_by_semicolon():
    # a step ending in `&` is its own separator: the next step must join with a
    # bare `\`-continuation, never `& ;` (which is a shell syntax error)
    out = assemble("echo a &\necho b")
    assert out == "arun echo a & \\\narun echo b"
    assert "& ;" not in out


def test_assemble_backgrounded_mid_chain_only_that_step():
    out = assemble("echo a\necho b &\necho c")
    assert out == "arun echo a ; \\\narun echo b & \\\narun echo c"


def test_assemble_backgrounded_last_step_keeps_trailing_amp():
    out = assemble("echo a\necho b &")
    assert out == "arun echo a ; \\\narun echo b &"


def test_assemble_double_amp_is_not_treated_as_background():
    # a trailing `&&` is a continuation folded in by split_commands, so the step
    # ends mid-command, not backgrounded -- the next step still joins with `;`
    out = assemble("echo a &&\necho b\necho c")
    assert out == "arun echo a &&\necho b ; \\\narun echo c"


def test_assemble_backgrounded_step_with_skew():
    out = assemble("rusthound x\nbloodhound y &\ncertipy z", skew_target="10.0.0.1")
    assert out == (
        "export AR_SKEW=10.0.0.1 ; \\\n"
        "arun rusthound x ; \\\n"
        "arun bloodhound y & \\\n"
        "arun certipy z"
    )


# ---------- shipped-cheat invariants ----------

# A command assembled into an arun chain is exec'd as argv ("exec $@"), never
# parsed by a shell, so a leading `NAME=val` env-assignment prefix would be taken
# as the program name (`exec: NAME=: not found`). Multi-command cheats must strip
# or unset env via a real command (e.g. `env -u FAKETIME ...`) instead. Regression
# guard for the `FAKETIME= bloodhound-ce-ctl` upload bug.
_ENV_ASSIGN_PREFIX = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _shipped_cheats():
    base = pathlib.Path(aliasr.__file__).parent / "data" / "cheats"
    for md in sorted(base.rglob("*.md")):
        cheats, _ = _parse_markdown(md, md.read_text(encoding="utf-8"))
        for ch in cheats:
            yield md, ch


def test_no_arun_chained_step_starts_with_env_assignment():
    offenders = []
    for md, ch in _shipped_cheats():
        steps = split_commands(ch.cmd)
        if len(steps) <= 1:
            continue  # single-command cheats emit bare and are shell-parsed
        for step in steps:
            first_token = step.lstrip().split(None, 1)[0] if step.strip() else ""
            if _ENV_ASSIGN_PREFIX.match(first_token):
                offenders.append(f"{md.name}: {ch.title!r}: {first_token}")
    assert not offenders, (
        "arun-chained steps with env-assignment prefix:\n" + "\n".join(offenders)
    )
