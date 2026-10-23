"""Tests for the shared Exegol-history hosts table + profile.sh host sync."""

import sqlite3

from aliasr.core import exegol
from aliasr.core.config import CREDS_DB
from aliasr.core.hosts import Host, load_hosts, save_hosts


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(str(CREDS_DB))


def test_host_splits_fqdn_into_hostname_and_domain():
    """The stored `hostname` field holds the FQDN; short name and domain are
    derived from it (a bare hostname with no domain keeps an empty domain)."""
    dc = Host("10.0.0.1", "DC01.corp.local", "DC")
    assert dc.short_hostname == "DC01"
    assert dc.domain == "corp.local"

    # Linux-style host: hostname but no domain.
    linux = Host("10.0.0.9", "web01", "")
    assert linux.short_hostname == "web01"
    assert linux.domain == ""

    # Deeper FQDN: only the first label is the hostname.
    sub = Host("10.0.0.2", "srv.ad.corp.local", "")
    assert sub.short_hostname == "srv"
    assert sub.domain == "ad.corp.local"


def test_discovered_host_globals_from_stored_dc():
    """discovered_host_globals maps a stored DC into the host globals, splitting
    its FQDN into hostname/domain and filling both target and dc fields."""
    from aliasr.core.hosts import clear_hosts, discovered_host_globals

    clear_hosts()
    exegol.clear_current_host()
    save_hosts([Host("10.0.0.1", "dc01.corp.local", "DC")])

    g = discovered_host_globals()
    assert g["ip"] == "10.0.0.1"
    assert g["fqdn"] == "dc01.corp.local"
    assert g["hostname"] == "dc01"
    assert g["domain"] == "corp.local"
    assert g["dc_ip"] == "10.0.0.1"
    assert g["dc_fqdn"] == "dc01.corp.local"


def test_save_and_load_hosts_roundtrip():
    save_hosts([Host("10.0.0.5", "web01.corp.local", ""), Host("10.0.0.1", "dc01.corp.local", "DC")])
    out = load_hosts()
    names = {h.hostname for h in out}
    assert "web01.corp.local" in names and "dc01.corp.local" in names
    dc = next(h for h in out if h.hostname == "dc01.corp.local")
    assert dc.role == "DC" and dc.ip == "10.0.0.1"


def test_write_hosts_upserts_without_deleting():
    save_hosts([Host("10.0.0.1", "dc01", "DC")])
    before = {h.hostname for h in load_hosts()}
    # Add a different host; the DC must survive (no replace-all).
    save_hosts([Host("10.0.0.9", "target", "")])
    after = {h.hostname for h in load_hosts()}
    assert {"dc01", "target"} <= after
    assert before <= after  # nothing dropped


def test_write_hosts_updates_role_on_conflict():
    save_hosts([Host("10.1.1.1", "box", "")])
    save_hosts([Host("10.1.1.1", "box", "DC")])  # same (ip, hostname)
    rows = [h for h in load_hosts() if h.hostname == "box" and h.ip == "10.1.1.1"]
    assert len(rows) == 1 and rows[0].role == "DC"


def test_clearing_credentials_leaves_hosts(tmp_path):
    from aliasr.core.creds import Credential, clear_creds
    save_hosts([Host("10.2.2.2", "keepme", "")])
    clear_creds()
    assert any(h.hostname == "keepme" for h in load_hosts())
    _ = Credential  # imported to mirror the creds/hosts separation under test


def test_profile_host_roundtrip_and_pinned_dc(tmp_path):
    prof = tmp_path / "profile.sh"
    # Set a DC, then a target; DC_* must stay pinned to the DC.
    exegol.set_current_host(dc_ip="10.0.0.1", dc_fqdn="dc01.corp.local", path=prof)
    exegol.set_current_host(ip="10.0.0.9", fqdn="web01.corp.local", path=prof)

    text = prof.read_text()
    assert "export IP='10.0.0.9'" in text
    assert "export TARGET='10.0.0.9'" in text  # TARGET mirrors IP
    assert "export DB_HOSTNAME='web01.corp.local'" in text
    assert "export DC_IP='10.0.0.1'" in text  # pinned, untouched by target set
    assert "export DC_HOST='dc01.corp.local'" in text

    cur = exegol.current_host(prof)
    assert cur == {
        "ip": "10.0.0.9",
        "fqdn": "web01.corp.local",
        "dc_ip": "10.0.0.1",
        "dc_fqdn": "dc01.corp.local",
    }


async def test_build_screen_defaults_host_from_current(app):
    from pathlib import Path

    from aliasr.tui.build_screen.build_screen import BuildScreen

    exegol.set_current_host(ip="10.10.10.10", fqdn="victim.corp.local")
    md = Path(next(c.path for c in app.cheats if c.path.endswith("protocols/ftp.md")))
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        await app.push_screen(BuildScreen("t", "nmap <ip> # <fqdn>", md))
        await pilot.pause()
        build = app.screen
        assert build._values.get("ip") == "10.10.10.10"
        assert build._values.get("fqdn") == "victim.corp.local"


def test_clear_hosts_wipes_table_and_unsets_profile():
    """`clear hosts` must empty the hosts table and unset the profile host vars,
    so nothing lingers to autofill."""
    from aliasr.core import exegol
    from aliasr.core.hosts import Host, clear_hosts, save_hosts

    save_hosts([Host("10.0.0.9", "web01", ""), Host("10.0.0.1", "dc01", "DC")])
    exegol.set_current_host(ip="10.0.0.9", fqdn="web01", dc_ip="10.0.0.1", dc_fqdn="dc01")
    assert load_hosts() and exegol.current_host()

    clear_hosts()
    assert load_hosts() == []
    assert exegol.current_host() == {}


def test_clear_hosts_leaves_credentials():
    from aliasr.core.creds import Credential, load_creds, save_creds
    from aliasr.core.hosts import Host, clear_hosts, save_hosts
    import time

    save_creds([Credential("admin", "p", "", "corp.local")])
    time.sleep(0.3)
    save_hosts([Host("10.0.0.5", "box", "")])
    clear_hosts()
    assert any(c.username == "admin" for c in load_creds())


def test_clear_flags_all_includes_hosts():
    """`clear all` wires hosts in alongside creds/globals/cache."""
    from aliasr.core.bootstrap import clear_flags
    from aliasr.core.hosts import Host, load_hosts, save_hosts

    save_hosts([Host("10.9.9.9", "late", "")])
    clear_flags(cache=False, globals=False, creds=True, hosts=True)
    assert load_hosts() == []
