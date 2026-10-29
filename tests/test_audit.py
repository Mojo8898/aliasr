"""CLI audit tests.

Guards against ``audit_config()`` drifting behind the config schema: every
user-facing ``config.toml`` section should be surfaced by ``aliasr audit
--config``. Also smoke-checks that each audit section (and the summary) runs
cleanly.
"""

import pytest

from aliasr.audit import run_audit_cli


@pytest.mark.parametrize(
    "kwargs",
    [
        {},  # bare summary
        {"cheats": True},
        {"cheats": True, "list_all": True},
        {"references": True},
        {"variations": True},
        {"config": True},
        {"run_all": True},
        {"references": True, "variations": True},  # composable
        {"list_all": True},  # implies cheats
    ],
)
def test_audit_sections_exit_clean(kwargs, capsys):
    """Every audit section (and the summary) returns 0 against the test config."""
    assert run_audit_cli(**kwargs) == 0


def test_audit_summary_covers_every_section(capsys):
    """Bare `audit` is a brief summary naming each section."""
    assert run_audit_cli() == 0
    out = capsys.readouterr().out
    assert "AUDIT SUMMARY" in out
    for section in ("Cheats", "References", "Variations", "Config"):
        assert section in out


def test_audit_config_covers_full_schema(capsys):
    """audit --config must surface every section/setting of config.toml."""
    rc = run_audit_cli(config=True)
    assert rc == 0

    out = capsys.readouterr().out

    # Section panels
    for panel in (
        "CHEATS CONFIGURATION",
        "GLOBALS CONFIGURATION",
        "CREDENTIALS CONFIGURATION",
        "NXC CONFIGURATION",
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
        "Block bulk NetExec deletion",
        "bindings defined across",  # keybindings summary line
    ):
        assert label in out, f"missing setting: {label}"
