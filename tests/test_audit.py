"""CLI audit tests.

Guards against ``audit_config()`` drifting behind the config schema: every
user-facing ``config.toml`` section should be surfaced by ``aliasr audit conf``.
Also smoke-checks that each audit subcommand runs cleanly.
"""

import pytest

from aliasr.audit import run_audit_cli


@pytest.mark.parametrize("which", [None, "refs", "vars", "conf"])
def test_audit_subcommands_exit_clean(which, capsys):
    """Every audit subcommand returns 0 against the (default) test config."""
    rc = run_audit_cli(list_all=False, which=which)
    assert rc == 0


def test_audit_config_covers_full_schema(capsys):
    """audit conf must surface every section/setting of config.toml."""
    rc = run_audit_cli(list_all=False, which="conf")
    assert rc == 0

    out = capsys.readouterr().out

    # Section panels
    for panel in (
        "CHEATS CONFIGURATION",
        "GLOBALS CONFIGURATION",
        "CREDENTIALS CONFIGURATION",
        "KEYBINDINGS CONFIGURATION",
        "BUILD CONFIGURATION",
        "THEME CONFIGURATION",
        "LAYOUT CONFIGURATION",
    ):
        assert panel in out, f"missing panel: {panel}"

    # Settings that previously went unreported (the drift this test guards)
    for label in (
        "Include bundled defaults",
        "Custom paths first",
        "Show globals grid",
        "Auto-calculate NT hash",
        "bindings defined across",  # keybindings summary line
    ):
        assert label in out, f"missing setting: {label}"


def test_audit_config_unknown_subcommand():
    """An unrecognized audit target returns non-zero."""
    assert run_audit_cli(list_all=False, which="bogus") == 1
