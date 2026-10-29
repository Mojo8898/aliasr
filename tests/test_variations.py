"""Per-line, collapsed variations for multi-line cheats.

Each placeholder resolves against its *own* line's command head. A placeholder
shared across lines collapses into a single choice whose keys are those common
to every occurrence, and one pick expands per command (e.g. Kerberos -> `-k` for
bloodyAD, `--use-kcache` for nxc). See aliasr/core/variations.py.
"""

import pytest

from aliasr.core import variations as V


@pytest.fixture
def loaded(monkeypatch):
    """Install a deterministic variation table (independent of shipped data)."""
    vars_ = {
        "bloodyAD": {
            "auth": {
                "Password": "-p '<password>'",
                "NT hash": "-p :<nt_hash>",
                "Kerberos": "-k",
            }
        },
        "nxc": {
            "auth": {
                "Password": "-p '<password>'",
                "NT hash": "-H <nt_hash>",
                "Kerberos": "--use-kcache",
            }
        },
        "certipy": {
            "auth": {
                "Password": "-p '<password>'",
                "NT hash": "-hashes <nt_hash>",
                "Kerberos": "-k",
            }
        },
    }
    univ = {"impacket_auth": {"Password": ":'<password>'", "Kerberos": " -k -no-pass"}}
    monkeypatch.setattr(V, "_VARS", vars_)
    monkeypatch.setattr(V, "_UNIVERSAL_VARS", univ)
    monkeypatch.setattr(V, "_LOADED", True)
    return vars_


_ALL_IN_ONE = (
    "bloodyAD --host <fqdn> -u '<user>' <auth> get writable\n"
    "nxc ldap <ip> -u '<user>' <auth> --bloodhound\n"
    "certipy find -u '<user>' <auth> -target <fqdn>"
)


def test_shared_auth_collapses_to_one_choice(loaded):
    got = V.get_all_variations(_ALL_IN_ONE, ["auth"])
    assert list(got) == ["auth"]  # one tab, not one per command
    assert [v.key for v in got["auth"]] == ["Password", "NT hash", "Kerberos"]
    # value carries the key (expansion is deferred to apply_selection)
    assert all(v.key == v.value for v in got["auth"])


def test_one_pick_expands_per_command(loaded):
    lines = V.apply_selection(_ALL_IN_ONE, {"auth": "Kerberos"}).split("\n")
    assert lines[0].endswith("-k get writable")  # bloodyAD
    assert "--use-kcache --bloodhound" in lines[1]  # nxc
    assert "-k -target <fqdn>" in lines[2]  # certipy


def test_collapse_keeps_only_keys_shared_by_every_command(loaded):
    # A key only some commands have must not appear in the collapsed choice.
    loaded["nxc"]["auth"]["Pass-the-ticket"] = "--use-kcache -k"
    got = V.get_all_variations("bloodyAD <auth> x\nnxc <auth> y", ["auth"])
    assert [v.key for v in got["auth"]] == ["Password", "NT hash", "Kerberos"]


def test_universal_param_is_an_independent_choice(loaded):
    cmd = (
        "nxc ldap <ip> <auth> --bloodhound\n"
        "GetNPUsers.py <domain>/<user><impacket_auth> -dc-host <fqdn>"
    )
    got = V.get_all_variations(cmd, ["auth", "impacket_auth"])
    assert set(got) == {"auth", "impacket_auth"}  # two separate tabs
    out = V.apply_selection(cmd, {"auth": "Kerberos", "impacket_auth": "Kerberos"})
    assert "--use-kcache --bloodhound" in out
    assert "<domain>/<user> -k -no-pass -dc-host" in out


def test_line_without_the_chosen_key_keeps_its_placeholder(loaded):
    loaded["nxc"]["auth"]["Pass-the-ticket"] = "--use-kcache -k"
    out = V.apply_selection(
        "nxc <auth> x\ncertipy <auth> y", {"auth": "Pass-the-ticket"}
    )
    assert "--use-kcache -k x" in out  # nxc has the key -> expanded
    assert "<auth> y" in out  # certipy lacks it -> untouched


def test_placeholder_on_a_command_with_no_table_is_not_offered(loaded):
    # hashcat has no auth set -> no tab, placeholder is a plain build field.
    got = V.get_all_variations("hashcat -m 18200 <auth> hashes", ["auth"])
    assert got == {}
