"""Tests for the Exegol-history profile.sh bridge (current-credential sharing).

The profile path is isolated to the temp ALIASR_PROFILE set by conftest; these
tests also pass explicit paths, so nothing here touches a real Exegol profile.
"""

from aliasr.core import exegol
from aliasr.core.creds import Credential


def test_set_then_read_roundtrip(tmp_path):
    prof = tmp_path / "profile.sh"
    exegol.set_current_credential(
        Credential("admin", "Pass123!", "AADHASH", "corp.local"), prof
    )

    cur = exegol.current_credential(prof)
    assert cur == Credential("admin", "Pass123!", "AADHASH", "corp.local")

    # Written in exegol's exact format.
    text = prof.read_text()
    assert "export USER='admin'" in text
    assert "export PASSWORD='Pass123!'" in text
    assert "export NT_HASH='AADHASH'" in text
    assert "export DOMAIN='corp.local'" in text


def test_ensure_profile_seeds_template_when_missing(tmp_path):
    prof = tmp_path / "nested" / "profile.sh"
    exegol.ensure_profile(prof)

    assert prof.exists()
    text = prof.read_text()
    # Commented template, no active credential yet.
    assert "#export USER=''" in text
    assert exegol.current_credential(prof) is None


def test_ensure_profile_does_not_clobber_existing(tmp_path):
    prof = tmp_path / "profile.sh"
    exegol.set_current_credential(Credential("admin", "pw", "", "corp"), prof)
    before = prof.read_text()

    exegol.ensure_profile(prof)
    assert prof.read_text() == before  # untouched
    assert exegol.current_credential(prof) == Credential("admin", "pw", "", "corp")


def test_single_quote_in_value_is_escaped(tmp_path):
    # A password containing ' must not break the single-quoted export line,
    # which would abort every shell sourcing the shared profile.sh.
    import subprocess

    prof = tmp_path / "profile.sh"
    exegol.set_current_credential(
        Credential("admin", "P@ss'word", "", "corp.local"), prof
    )

    # The file must source cleanly in a real shell...
    r = subprocess.run(["bash", "-c", f". {prof}"], capture_output=True)
    assert r.returncode == 0, r.stderr

    # ...and the value must come back intact.
    cur = exegol.current_credential(prof)
    assert cur is not None
    assert cur.password == "P@ss'word"


def test_updates_existing_template_lines_only(tmp_path):
    prof = tmp_path / "profile.sh"
    prof.write_text(
        "#info: buffer\n"
        "#export USER='someuser'\n"
        "#export PASSWORD='somepassword'\n"
        "#export NT_HASH='deadbeef'\n"
        "#export DOMAIN='DOMAIN.LOCAL'\n"
        "#export IP='192.168.56.69'\n"
    )
    exegol.set_current_credential(Credential("neo", "red", "", "matrix.local"), prof)

    text = prof.read_text()
    assert "export USER='neo'" in text
    assert "export PASSWORD='red'" in text
    assert "unset NT_HASH" in text  # empty field -> unset, like exegol
    assert "export DOMAIN='matrix.local'" in text
    assert "#export IP='192.168.56.69'" in text  # unrelated var untouched


def test_commented_profile_means_no_current_cred(tmp_path):
    prof = tmp_path / "profile.sh"
    prof.write_text("#export USER='someuser'\n#export PASSWORD='p'\n")
    assert exegol.current_credential(prof) is None


def test_missing_profile_returns_none(tmp_path):
    assert exegol.current_credential(tmp_path / "nope.sh") is None


async def test_build_screen_defaults_to_current_cred(app):
    """A built command's cred params prefill from the exegol current credential."""
    from pathlib import Path

    from aliasr.tui.build_screen.build_screen import BuildScreen

    exegol.set_current_credential(Credential("neo", "trinity", "", "matrix.local"))

    md = Path(next(c.path for c in app.cheats if c.path.endswith("protocols/ftp.md")))
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        await app.push_screen(BuildScreen("t", "ftp <user> -p <password>", md))
        await pilot.pause()
        build = app.screen
        assert build._values.get("user") == "neo"
        assert build._values.get("password") == "trinity"


def test_clear_creds_also_unsets_profile_credential():
    """`clear creds` must unset the profile.sh credential, not just the DB row,
    so it stops autofilling after a clear."""
    from aliasr.core import exegol
    from aliasr.core.creds import Credential, clear_creds

    exegol.set_current_credential(Credential("admin", "p", "", "corp.local"))
    assert exegol.current_credential() is not None

    clear_creds()
    assert exegol.current_credential() is None
