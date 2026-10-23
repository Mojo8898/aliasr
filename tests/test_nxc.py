"""Tests for the live NetExec (nxcdb) credential integration.

These build a throwaway ~/.nxc tree with real SQLite files shaped like
NetExec's protocol databases, point ``ALIASR_NXC_HOME`` at it, and assert that:
  * credentials are pulled into aliasr's shared store on first load, and
  * deleting a NetExec-sourced credential in aliasr deletes it from NetExec too,
    while hand-entered credentials and the NetExec DB are otherwise untouched.
"""
import sqlite3
import textwrap

import pytest

from aliasr.core import creds as creds_mod
from aliasr.core import exegol
from aliasr.core import hosts as hosts_mod
from aliasr.core import nxc
from aliasr.core.creds import (
    Credential,
    clear_creds,
    load_creds,
    save_creds,
)
from aliasr.core.hosts import (
    Host,
    clear_hosts,
    load_hosts,
    reconcile_hosts,
)


# NetExec protocol-DB DDL (trimmed to the columns aliasr reads), matching
# nxc 1.5.x. Every protocol DB shares the same `users` shape.
_USERS_DDL = """
CREATE TABLE users (
    id INTEGER NOT NULL, domain VARCHAR, username VARCHAR, password VARCHAR,
    credtype VARCHAR, pillaged_from_hostid INTEGER, PRIMARY KEY (id)
);
"""


# smb.db carries the `dc` flag; other protocol DBs omit it.
_SMB_DDL = _USERS_DDL + """
CREATE TABLE hosts (
    id INTEGER NOT NULL, ip VARCHAR, hostname VARCHAR, domain VARCHAR,
    os VARCHAR, dc BOOLEAN, PRIMARY KEY (id), UNIQUE (ip)
);
"""


def _make_db(path, users=(), hosts=()):
    """Write a NetExec-shaped protocol DB. `users` rows are
    (domain, username, password, credtype); `hosts` rows are
    (ip, hostname, domain, os, dc)."""
    conn = sqlite3.connect(str(path))
    conn.executescript(_SMB_DDL if hosts else _USERS_DDL)
    conn.executemany(
        "INSERT INTO users (domain, username, password, credtype) VALUES (?,?,?,?)",
        users,
    )
    if hosts:
        conn.executemany(
            "INSERT INTO hosts (ip, hostname, domain, os, dc) VALUES (?,?,?,?,?)",
            hosts,
        )
    conn.commit()
    conn.close()


def _users(db):
    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT domain, username, credtype FROM users").fetchall()
    conn.close()
    return rows


def _hosts(db):
    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT ip, hostname FROM hosts").fetchall()
    conn.close()
    return rows


@pytest.fixture
def nxc_home(tmp_path, monkeypatch):
    """A fake ~/.nxc with a 'default' workspace, wired via ALIASR_NXC_HOME.

    Also resets the process-global credential state (memo + the once-per-process
    NetExec pull) so each test pulls freshly from its own workspace.
    """
    home = tmp_path / ".nxc"
    ws = home / "workspaces" / "default"
    ws.mkdir(parents=True)
    (home / "nxc.conf").write_text(
        textwrap.dedent("""
            [nxc]
            workspace = default
        """).strip() + "\n"
    )
    monkeypatch.setenv("ALIASR_NXC_HOME", str(home))

    def _reset():
        clear_creds()
        clear_hosts()
        creds_mod._MEMO = None
        creds_mod._NXC_KEYS = None
        hosts_mod._NXC_KEYS = None

    _reset()
    yield ws
    _reset()


# ---------- read / map ----------


def test_read_creds_maps_plaintext_and_hash(nxc_home):
    nt = "A" * 32
    _make_db(
        nxc_home / "smb.db",
        users=[("corp.local", "admin", "Passw0rd!", "plaintext"),
               ("corp.local", "svc", f"{'0' * 32}:{nt.lower()}", "hash")],
    )
    got = {c.username: c for c in nxc.read_creds("default")}
    assert got["admin"].password == "Passw0rd!" and got["admin"].hash == ""
    assert got["svc"].hash == nt and got["svc"].password == ""  # NT half, upper-cased


def test_read_creds_dedups_across_protocol_dbs(nxc_home):
    user = ("corp.local", "admin", "Passw0rd!", "plaintext")
    _make_db(nxc_home / "smb.db", users=[user])
    _make_db(nxc_home / "ldap.db", users=[user])
    assert len(nxc.read_creds("default")) == 1


def test_read_creds_empty_when_home_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("ALIASR_NXC_HOME", str(tmp_path / "nope"))
    assert nxc.read_creds("default") == []


# ---------- startup pull ----------


def test_load_pulls_nxc_creds_into_store(nxc_home):
    _make_db(nxc_home / "smb.db",
             users=[("corp.local", "admin", "Passw0rd!", "plaintext")])
    loaded = {c.username for c in load_creds()}
    assert "admin" in loaded


def test_pull_preserves_hand_entered_creds(nxc_home):
    # Seed a hand-entered cred synchronously (save_creds writes on a thread).
    creds_mod._db.write([Credential("existing", "secret", "", "corp.local")])
    _make_db(nxc_home / "smb.db",
             users=[("corp.local", "admin", "Passw0rd!", "plaintext")])
    loaded = {c.username for c in load_creds()}
    assert {"existing", "admin"} <= loaded


# ---------- delete propagation ----------


def test_delete_in_aliasr_removes_from_nxc(nxc_home):
    db = nxc_home / "smb.db"
    _make_db(db, users=[("corp.local", "admin", "Passw0rd!", "plaintext"),
                        ("corp.local", "keep", "pw", "plaintext")])
    rows = load_creds()
    assert {"admin", "keep"} <= {c.username for c in rows}

    # Drop 'admin' and save the survivors, as the creds screen does on close.
    survivors = [c for c in rows if c.username != "admin"]
    save_creds(survivors)

    remaining = {u for _, u, _ in _users(db)}
    assert "admin" not in remaining  # propagated out of NetExec
    assert "keep" in remaining       # untouched


def test_delete_propagates_across_all_protocol_dbs(nxc_home):
    user = ("corp.local", "admin", "Passw0rd!", "plaintext")
    smb, ldap = nxc_home / "smb.db", nxc_home / "ldap.db"
    _make_db(smb, users=[user])
    _make_db(ldap, users=[user])

    rows = load_creds()
    save_creds([c for c in rows if c.username != "admin"])

    assert _users(smb) == [] and _users(ldap) == []


def test_deleting_non_nxc_cred_leaves_nxc_alone(nxc_home):
    db = nxc_home / "smb.db"
    _make_db(db, users=[("corp.local", "admin", "Passw0rd!", "plaintext")])
    rows = load_creds()  # pulls 'admin'; records it as NetExec-sourced

    # Add a hand-entered cred, then remove it. 'admin' is present in both
    # saves, so only 'temp' churns and NetExec is never touched.
    save_creds(rows + [Credential("temp", "x", "", "corp.local")])
    save_creds(rows)

    assert "admin" in {u for _, u, _ in _users(db)}


def test_empty_domain_merge_does_not_spuriously_delete(nxc_home):
    """A NetExec cred with no domain that merges into an existing domained cred
    must not be deleted from NetExec when the user saves an unrelated change."""
    # exh has admin@CORP; NetExec has admin with empty domain -> they merge.
    creds_mod._db.write([Credential("admin", "pw", "", "CORP")])
    db = nxc_home / "smb.db"
    _make_db(db, users=[("", "admin", "pw", "plaintext"),
                        ("CORP", "other", "x", "plaintext")])
    rows = load_creds()
    assert "admin" in {c.username for c in rows}

    save_creds(rows)  # save without touching admin

    assert "admin" in {u for _, u, _ in _users(db)}  # not spuriously deleted


def test_clear_creds_wipes_nxc_by_default(nxc_home):
    db = nxc_home / "smb.db"
    _make_db(db, users=[("corp.local", "admin", "Passw0rd!", "plaintext")])
    load_creds()
    clear_creds()
    # Default: a bulk clear empties NetExec's credential store too.
    assert _users(db) == []


def test_clear_creds_respects_block_bulk_delete(nxc_home, monkeypatch):
    monkeypatch.setattr("aliasr.core.config.NXC_BLOCK_BULK_DELETE", True)
    db = nxc_home / "smb.db"
    _make_db(db, users=[("corp.local", "admin", "Passw0rd!", "plaintext")])
    load_creds()
    clear_creds()
    # With the guard set, the bulk wipe must not reach NetExec.
    assert "admin" in {u for _, u, _ in _users(db)}


# ---------- UI path (Pilot) ----------


async def test_creds_screen_delete_propagates_to_nxc(app, nxc_home):
    """Deleting a NetExec-sourced row in the creds screen and closing it removes
    the row from NetExec — the real on_unmount -> save_creds -> delete chain.

    `app` is built (and its creds primed) before `nxc_home` resets the pull
    state, so the screen's own load_creds re-pulls from this test's workspace.
    """
    from aliasr.tui.creds_screen.creds_screen import CredsScreen

    db = nxc_home / "smb.db"
    _make_db(db, users=[("corp.local", "admin", "Passw0rd!", "plaintext")])

    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        await app.push_screen(CredsScreen())
        await pilot.pause()
        screen = app.screen
        assert screen._tab == "creds"  # creds tab shown by default
        assert "admin" in {c.username for c in screen._rows["creds"]}  # pulled in

        screen.action_delete_row()   # opens the confirm prompt
        await pilot.pause()
        await pilot.press("y")        # confirm -> removes the row
        await pilot.pause()
        await app.pop_screen()        # fires on_unmount -> save_creds([])
        await pilot.pause()

    assert _users(db) == []


# ---------- hosts: read / pull / delete / clear ----------


def test_read_hosts_maps_fqdn_and_dc(nxc_home):
    _make_db(
        nxc_home / "smb.db",
        hosts=[("10.0.0.1", "DC01", "corp.local", "Server 2019", 1),
               ("10.0.0.5", "WEB01", "corp.local", "Server 2016", 0)],
    )
    by_ip = {h.ip: h for h in nxc.read_hosts("default")}
    assert by_ip["10.0.0.1"].hostname == "DC01.corp.local"
    assert by_ip["10.0.0.1"].role == "DC"
    assert by_ip["10.0.0.5"].role == ""  # not a DC


def test_load_pulls_nxc_hosts_into_store(nxc_home):
    _make_db(nxc_home / "smb.db", hosts=[("10.0.0.1", "DC01", "corp.local", "", 1)])
    names = {h.hostname for h in load_hosts()}
    assert "DC01.corp.local" in names


def test_reconcile_delete_propagates_host_to_nxc(nxc_home):
    db = nxc_home / "smb.db"
    _make_db(db, hosts=[("10.0.0.1", "DC01", "corp.local", "", 1),
                        ("10.0.0.5", "WEB01", "corp.local", "", 0)])
    rows = load_hosts()
    assert {"10.0.0.1", "10.0.0.5"} <= {h.ip for h in rows}

    survivors = [h for h in rows if h.ip != "10.0.0.5"]
    reconcile_hosts(survivors)  # the hosts menu's save-on-close

    remaining = {ip for ip, _ in _hosts(db)}
    assert "10.0.0.5" not in remaining and "10.0.0.1" in remaining


def test_renaming_host_does_not_delete_it_from_nxc(nxc_home):
    """Editing a host's hostname (ip unchanged) updates it in place and must NOT
    propagate a delete to NetExec, which keys/deletes hosts by ip."""
    db = nxc_home / "smb.db"
    _make_db(db, hosts=[("10.0.0.1", "DC01", "corp.local", "", 1)])
    row = next(h for h in load_hosts() if h.ip == "10.0.0.1")

    reconcile_hosts([Host("10.0.0.1", "DC01-RENAMED", row.role, row.host_id)])

    assert "10.0.0.1" in {ip for ip, _ in _hosts(db)}  # survived in NetExec


def test_clear_hosts_wipes_nxc_by_default(nxc_home):
    db = nxc_home / "smb.db"
    _make_db(db, hosts=[("10.0.0.1", "DC01", "corp.local", "", 1)])
    load_hosts()
    clear_hosts()
    assert _hosts(db) == []


def test_clear_hosts_respects_block_bulk_delete(nxc_home, monkeypatch):
    monkeypatch.setattr("aliasr.core.config.NXC_BLOCK_BULK_DELETE", True)
    db = nxc_home / "smb.db"
    _make_db(db, hosts=[("10.0.0.1", "DC01", "corp.local", "", 1)])
    load_hosts()
    clear_hosts()
    assert {ip for ip, _ in _hosts(db)} == {"10.0.0.1"}


async def test_hosts_tab_delete_propagates_to_nxc(app, nxc_home):
    """Switching to the hosts tab, deleting a NetExec host and closing removes
    it from NetExec (the on_unmount -> reconcile_hosts -> delete chain)."""
    from aliasr.tui.creds_screen.creds_screen import CredsScreen

    db = nxc_home / "smb.db"
    _make_db(db, hosts=[("10.0.0.1", "DC01", "corp.local", "", 1)])

    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        await app.push_screen(CredsScreen())
        await pilot.pause()
        screen = app.screen

        # Copy keys are shared; on the creds tab the creds set is enabled and
        # the host set is dropped (False, so it leaves the footer entirely).
        assert screen.check_action("copy_user", ()) is True
        assert screen.check_action("copy_ip", ()) is False

        screen.action_next_tab()  # alt+right -> hosts tab
        await pilot.pause()
        assert screen._tab == "hosts"
        assert "10.0.0.1" in {h.ip for h in screen._rows["hosts"]}

        # ...and the host set takes over on the hosts tab.
        assert screen.check_action("copy_ip", ()) is True
        assert screen.check_action("copy_user", ()) is False

        screen.action_delete_row()
        await pilot.pause()
        await pilot.press("y")  # confirm the deletion
        await pilot.pause()
        await app.pop_screen()  # on_unmount -> reconcile_hosts([])
        await pilot.pause()

    assert _hosts(db) == []


async def test_delete_prompt_cancel_keeps_the_row(app, nxc_home):
    """Answering 'n' at the confirm prompt leaves the credential (and nxcdb) intact."""
    from aliasr.tui.creds_screen.creds_screen import CredsScreen

    db = nxc_home / "smb.db"
    _make_db(db, users=[("corp.local", "admin", "Passw0rd!", "plaintext")])

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await app.push_screen(CredsScreen())
        await pilot.pause()
        screen = app.screen

        screen.action_delete_row()
        await pilot.pause()
        await pilot.press("n")   # cancel
        await pilot.pause()
        assert "admin" in {c.username for c in screen._rows["creds"]}
        await app.pop_screen()
        await pilot.pause()

    assert "admin" in {u for _, u, _ in _users(db)}


async def test_copy_keys_remap_between_tabs(app, nxc_home, monkeypatch):
    """The same copy keys target different columns per tab: ctrl+r/ctrl+t copy
    username/password on the creds tab and ip/hostname on the hosts tab."""
    import aliasr.core.inject as inject
    from aliasr.tui.creds_screen.creds_screen import CredsScreen

    captured: list[str] = []
    monkeypatch.setattr(inject, "copy_to_clipboard", lambda v: captured.append(v))

    _make_db(
        nxc_home / "smb.db",
        users=[("corp.local", "admin", "Passw0rd!", "plaintext")],
        hosts=[("10.0.0.1", "DC01", "corp.local", "", 1)],
    )

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await app.push_screen(CredsScreen())
        await pilot.pause()
        screen = app.screen

        def labels():
            ab = screen.active_bindings
            return {k: (ab[k].binding.description, ab[k].enabled)
                    for k in ("ctrl+r", "ctrl+t") if k in ab}

        # Creds tab (default): ctrl+r -> username, ctrl+t -> password, and the
        # footer labels them so (not greyed-out creds labels on the wrong tab).
        assert labels() == {"ctrl+r": ("Copy User", True),
                            "ctrl+t": ("Copy Password", True)}
        await pilot.press("ctrl+r")
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert captured[-2:] == ["admin", "Passw0rd!"]

        screen.action_next_tab()
        await pilot.pause()
        # Hosts tab: the same keys now copy ip / hostname, footer relabelled.
        assert labels() == {"ctrl+r": ("Copy IP", True),
                            "ctrl+t": ("Copy Hostname", True)}
        await pilot.press("ctrl+r")
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert captured[-2:] == ["10.0.0.1", "DC01.corp.local"]


# ---------- confirm-delete toggle & CLI clear confirmation ----------


async def test_confirm_delete_can_be_disabled(app, nxc_home, monkeypatch):
    """[creds] confirm_delete = false deletes a row immediately, no prompt."""
    monkeypatch.setattr("aliasr.core.config.CREDS_CONFIRM_DELETE", False)
    from aliasr.tui.creds_screen.creds_screen import CredsScreen
    from aliasr.tui.creds_screen.confirm import ConfirmDelete

    _make_db(nxc_home / "smb.db", users=[("corp.local", "admin", "pw", "plaintext")])

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await app.push_screen(CredsScreen())
        await pilot.pause()
        screen = app.screen

        screen.action_delete_row()
        await pilot.pause()
        assert not isinstance(app.screen, ConfirmDelete)  # no prompt
        assert "admin" not in {c.username for c in screen._rows["creds"]}


def test_clear_flags_reports_cleared_vs_unchanged(nxc_home, capsys):
    from aliasr.core.bootstrap import clear_flags

    # Empty store -> "unchanged".
    clear_flags(cache=False, globals=False, creds=True)
    assert "Credentials unchanged" in capsys.readouterr().out

    # Populated store -> "cleared successfully!".
    creds_mod._db.write([Credential("admin", "pw", "", "corp")])
    clear_flags(cache=False, globals=False, creds=True)
    assert "Credentials cleared successfully!" in capsys.readouterr().out


def test_confirm_clear_allows_nondestructive_and_yes():
    from aliasr.core.bootstrap import confirm_clear

    assert confirm_clear("cache") is True       # non-destructive: no prompt
    assert confirm_clear("globals") is True
    assert confirm_clear("creds", assume_yes=True) is True  # --yes skips prompt


def test_confirm_clear_prompts_on_destructive(monkeypatch):
    from aliasr.core import bootstrap

    # Force "there is something to clear" so we exercise the prompt itself.
    monkeypatch.setattr(bootstrap, "_has_clearable_data", lambda _cmd: True)

    monkeypatch.setattr("builtins.input", lambda *_: "n")
    assert bootstrap.confirm_clear("creds") is False   # declined

    monkeypatch.setattr("builtins.input", lambda *_: "y")
    assert bootstrap.confirm_clear("all") is True       # confirmed

    def _eof(*_):
        raise EOFError

    monkeypatch.setattr("builtins.input", _eof)
    assert bootstrap.confirm_clear("hosts") is False    # non-interactive aborts


def test_confirm_clear_skips_prompt_when_empty(monkeypatch):
    from aliasr.core import bootstrap

    monkeypatch.setattr(bootstrap, "_has_clearable_data", lambda _cmd: False)

    def _boom(*_):
        raise AssertionError("should not prompt when there is nothing to clear")

    monkeypatch.setattr("builtins.input", _boom)
    assert bootstrap.confirm_clear("creds") is True  # proceeds without asking


# ---------- deleting the current credential/host reconciles profile.sh ----------


async def test_deleting_current_credential_clears_profile(app, nxc_home):
    """Deleting the credential that profile.sh currently points at unsets it
    there too (the ctrl+c-after-delete bug)."""
    from aliasr.tui.creds_screen.creds_screen import CredsScreen

    creds_mod._db.write([Credential("admin", "pw", "", "corp.local")])
    exegol.set_current_credential(Credential("admin", "pw", "", "corp.local"))
    assert exegol.current_credential() is not None

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await app.push_screen(CredsScreen())
        await pilot.pause()
        app.screen.action_delete_row()
        await pilot.pause()
        await pilot.press("y")        # confirm
        await pilot.pause()
        await app.pop_screen()        # on_unmount
        await pilot.pause()

    assert exegol.current_credential() is None


async def test_deleting_other_credential_keeps_current(app, nxc_home):
    """Deleting a different credential must not disturb the current one."""
    from aliasr.tui.creds_screen.creds_screen import CredsScreen

    creds_mod._db.write([
        Credential("keepme", "pw", "", "corp.local"),
        Credential("victim", "x", "", "corp.local"),
    ])
    exegol.set_current_credential(Credential("keepme", "pw", "", "corp.local"))

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await app.push_screen(CredsScreen())
        await pilot.pause()
        s = app.screen
        s.action_list_down()          # highlight 'victim' (row 1)
        await pilot.pause()
        s.action_delete_row()
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        await app.pop_screen()
        await pilot.pause()

    cur = exegol.current_credential()
    assert cur is not None and cur.username == "keepme"


async def test_deleting_current_host_clears_profile_target(app, nxc_home):
    """Deleting the current target host unsets the target vars in profile.sh."""
    from aliasr.tui.creds_screen.creds_screen import CredsScreen

    creds_mod._db.write_hosts([Host("10.0.0.9", "web.corp.local", "")])
    exegol.set_current_host(ip="10.0.0.9", fqdn="web.corp.local")
    assert exegol.current_host().get("ip") == "10.0.0.9"

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        await app.push_screen(CredsScreen())
        await pilot.pause()
        s = app.screen
        s.action_next_tab()           # hosts tab
        await pilot.pause()
        s.action_delete_row()
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        await app.pop_screen()
        await pilot.pause()

    assert "ip" not in exegol.current_host()
