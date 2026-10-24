"""Deeper Pilot coverage: exercise the flows a smoke test skips.

These mount each modal screen and run the search filter, so a runtime break in
a deeper path (not just boot) surfaces as a failing test rather than a silent
regression. This is the net that catches a Textual-version breakage.
"""

from textual.widgets import Input

from aliasr.tui.main_screen.main_screen import MainScreen
from aliasr.tui.creds_screen.creds_screen import CredsScreen
from aliasr.tui.globals_screen.globals_screen import GlobalsScreen


async def test_cheats_populate_on_boot(app):
    """Regression guard for the Textual-8 Select.NULL break.

    The empty-Select sentinel changed (BLANK -> NULL), which made the target/OS
    filter reject every cheat, emptying the whole app. With bundled cheats on
    disk, the main screen must show matches on boot with no filters applied.
    """
    assert app.cheats, "fixture should load bundled cheats"
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.matches, "no cheats visible on boot — Select filter regressed"


async def test_search_filter_runs(app):
    """Typing in the search box runs refresh_matches (exercises the Select filter)."""
    async with app.run_test() as pilot:
        await pilot.pause()
        search = app.query_one("#search", Input)
        search.focus()
        await pilot.pause()
        await pilot.press("s", "m", "b")  # narrow the cheat list
        await pilot.pause()
        # No exception == the Select.BLANK/NULL filter path is intact.
        assert isinstance(app.screen, MainScreen)


async def test_tab_switch_updates_matches(app):
    """Switching tabs (Tabs.TabActivated path) re-filters without error.

    Tabs activation behavior shifted in Textual 8; this guards that path.
    """
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.matches
        await pilot.press("alt+right")
        await pilot.pause()
        assert app.screen.current_tag != "all"  # moved off the first tab


async def test_tag_filter_hides_tabs(app):
    """The tag filter hides non-matching tabs and keeps the active tab visible.

    CheatTags toggles the -hidden class itself (not Tabs.show/hide), so this
    guards that a hidden active tab still hands off to a visible one.
    """
    from textual.widgets import Tab

    async with app.run_test() as pilot:
        await pilot.pause()
        tabs = app.screen.query_one("#tabs")

        def visible() -> list[Tab]:
            return [t for t in tabs.query(Tab) if not t.has_class("-hidden")]

        total = len(visible())
        assert tabs.active == "tab-all"

        app.screen.query_one("#tag-filter", Input).focus()
        await pilot.press("a", "w", "s")
        await pilot.pause()
        shown = visible()
        assert 0 < len(shown) < total
        assert all("aws" in str(t.label) for t in shown)  # "all" is hidden too
        assert tabs.active in {t.id for t in shown}
        assert app.screen.current_tag == tabs._id_to_tag[tabs.active]

        await pilot.press("backspace", "backspace", "backspace")
        await pilot.pause()
        assert len(visible()) == total
        assert tabs.active == "tab-all"


async def test_globals_screen_mounts(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.push_screen(GlobalsScreen())
        await pilot.pause()
        assert isinstance(app.screen, GlobalsScreen)


async def test_creds_screen_mounts(app):
    async with app.run_test() as pilot:
        await pilot.pause()
        await app.push_screen(CredsScreen())
        await pilot.pause()
        assert isinstance(app.screen, CredsScreen)


async def test_build_screen_flow(app):
    """Open the build screen for the first matching cheat (variations or not)."""
    async with app.run_test() as pilot:
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, MainScreen)
        assert screen.matches, "expected bundled cheats to be loaded"
        screen.selected_idx = 0
        await screen.run_action("build_screen")
        await pilot.pause()
        # Either VariationsScreen or BuildScreen is now on top; just assert we left main.
        assert not isinstance(app.screen, MainScreen)


async def test_ctrl_t_no_longer_opens_a_screen(app):
    """The tree/file-picker screen was removed; ctrl+t must not push anything.

    It used to be bound on the globals grid, so press it with a global focused.
    """
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        screen = app.screen
        screen._set_grid_visible(True)
        await pilot.pause()
        first_global = screen._first_globals_input()
        assert first_global is not None, "expected default globals in the grid"
        first_global.focus()
        await pilot.pause()
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)


async def test_focus_grid_binding_tracks_grid_visibility(app):
    """'Focus Grid' is only offered (and shown in the footer) while the grid is visible."""
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        screen = app.screen
        screen._set_grid_visible(True)
        await pilot.pause()
        assert screen.check_action("cycle_grid_focus", ())
        assert "Focus Grid" in _footer_labels(screen)

        await screen.run_action("toggle_grid")
        await pilot.pause()
        assert not screen.globals_panel.display
        assert not screen.check_action("cycle_grid_focus", ())
        assert "Focus Grid" not in _footer_labels(screen)


def _footer_labels(screen) -> set[str]:
    return {b.description for _, b, enabled, _ in screen.active_bindings.values() if enabled}


async def test_param_pick_does_not_reopen_autocomplete(app):
    """Picking a value in ParamScreen fills the input without popping the dropdown.

    Setting the value used to post Input.Changed, which re-opened the path
    autocomplete for values like '/tmp' after returning to the build screen.
    """
    from pathlib import Path

    from aliasr.tui.build_screen.build_screen import BuildScreen
    from aliasr.tui.build_screen.param_screen import ParamScreen
    from aliasr.tui.utils.smart_complete import SmartComplete

    # A bundled cheat file that defines references for <lin_dir>, so the
    # param screen has options and stays open.
    md = Path(next(c.path for c in app.cheats if c.path.endswith("linux/linux_privesc.md")))
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        await app.push_screen(BuildScreen("t", "cd <lin_dir>", md))
        await pilot.pause()
        build = app.screen
        inp = build._inputs[0]
        inp.focus()
        await pilot.pause()

        build.action_param_screen()
        await pilot.pause()
        assert isinstance(app.screen, ParamScreen)
        app.screen.dismiss("/tmp")
        for _ in range(3):
            await pilot.pause()

        sc = build.query_one(SmartComplete)
        assert app.focused is inp
        assert inp.value == "/tmp"
        assert build._values["lin_dir"] == "/tmp"
        assert not sc.display, "autocomplete dropdown re-opened after param selection"


def test_creds_drops_row_reordering_globals_keeps_it():
    """Reordering was removed from creds (shared DB has no row order) but remains
    on the globals grid (ordered lists in globals.json)."""
    from aliasr.tui.creds_screen.creds_screen import CredsScreen
    from aliasr.tui.globals_screen.globals_screen import GlobalsScreen

    def actions(screen_cls):
        return {getattr(b, "action", None) for b in screen_cls.BINDINGS}

    creds_actions = actions(CredsScreen)
    assert "move_row_up" not in creds_actions
    assert "move_row_down" not in creds_actions
    assert not hasattr(CredsScreen, "action_move_row_up")
    assert not hasattr(CredsScreen, "_move_row")

    globals_actions = actions(GlobalsScreen)
    assert "move_row_up" in globals_actions
    assert "move_row_down" in globals_actions


def test_oneline_joins_commands_with_semicolon():
    """The one-row cheat preview joins newline-separated commands with '; ' and
    collapses a '\\' continuation (within one command) to a space."""
    from aliasr.tui.main_screen.cheatlist import CheatCommandList

    cl = CheatCommandList()
    # commands on separate lines -> joined with "; "
    assert (
        cl._one_line("rm /tmp/x\nnxc smb <ip>\ntee out")
        == "rm /tmp/x; nxc smb <ip>; tee out"
    )
    # a "\"-continued single command collapses to a space (stays one segment)
    assert cl._one_line("a \\\nb") == "a b"
    # CRLF corpus variant, continuation + boundary
    assert cl._one_line("a \\\r\nb\r\nc") == "a b; c"
    # single command untouched
    assert cl._one_line("nxc smb <ip>") == "nxc smb <ip>"


async def test_build_preview_scrolls_and_panel_fits(app):
    """A long (multi-line) command must scroll inside its own #preview-scroll box
    rather than growing the panel past the screen edges."""
    from pathlib import Path
    from textual.containers import VerticalScroll
    from aliasr.tui.build_screen.build_screen import BuildScreen

    long_cmd = "\n".join(f"step{i} <ip> -u <user> ; \\" for i in range(25)) + "\nfinal <ip>"
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        screen = BuildScreen("Test", long_cmd, Path("x.md"))
        await app.push_screen(screen)
        await pilot.pause()
        await pilot.pause()
        panel = screen.query_one("#panel")
        ps = screen.query_one("#preview-scroll", VerticalScroll)
        # Panel stays within the screen; preview box is capped and scrollable.
        assert 0 <= panel.region.y and panel.region.bottom <= app.size.height
        assert ps.max_scroll_y > 0, "long command should overflow the capped preview"
        assert not ps.can_focus, "preview box should stay out of the Tab cycle"
        ps.scroll_end(animate=False)
        await pilot.pause()
        assert ps.scroll_offset.y == ps.max_scroll_y


async def test_variations_panel_fits_and_options_visible(app):
    """Regression for the variations modal overflowing the screen and hiding its
    options: the panel must fit and the option list must be visible on-screen."""
    from textual.containers import VerticalScroll
    from textual.widgets import OptionList
    from aliasr.tui.build_screen.variations_screen import VariationsScreen
    from aliasr.core.variations import Variation

    long_cmd = "\n".join(f"step{i} <ip> ; \\" for i in range(25)) + "\nfinal <ip>"
    variations = {"ip": [Variation(f"host{i}", f"10.0.0.{i}", "ip", "") for i in range(30)]}
    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        screen = VariationsScreen(long_cmd, variations)
        await app.push_screen(screen)
        await pilot.pause()
        await pilot.pause()
        panel = screen.query_one("#panel")
        ps = screen.query_one("#preview-scroll", VerticalScroll)
        lst = screen.query_one("#ip-list", OptionList)
        assert 0 <= panel.region.y and panel.region.bottom <= app.size.height
        assert ps.max_scroll_y > 0
        assert lst.option_count == 30
        assert lst.region.height > 0 and lst.region.bottom <= app.size.height


async def test_variations_preview_is_head_aware(app, monkeypatch):
    """A single collapsed auth pick renders per command in the live preview:
    `-k` on the bloodyAD line, `--use-kcache` on the nxc line, at once."""
    from textual.widgets import Static
    from aliasr.tui.build_screen.variations_screen import VariationsScreen
    from aliasr.core import variations as V

    monkeypatch.setattr(V, "_VARS", {
        "bloodyAD": {"auth": {"Password": "-p '<password>'", "Kerberos": "-k"}},
        "nxc": {"auth": {"Password": "-p '<password>'", "Kerberos": "--use-kcache"}},
    })
    monkeypatch.setattr(V, "_UNIVERSAL_VARS", {})
    monkeypatch.setattr(V, "_LOADED", True)

    cmd = "bloodyAD <auth> get\nnxc ldap <auth> --bloodhound"
    all_vars = V.get_all_variations(cmd, ["auth"])
    assert list(all_vars) == ["auth"]  # collapsed to one tab

    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        screen = VariationsScreen(cmd, all_vars)
        await app.push_screen(screen)
        await pilot.pause()
        await pilot.pause()

        screen._preview_values["auth"] = "Kerberos"
        screen._update_preview()
        await pilot.pause()

        rendered = screen.query_one("#preview", Static).render()
        plain = rendered.plain if hasattr(rendered, "plain") else str(rendered)
        assert "-k get" in plain                      # bloodyAD line
        assert "--use-kcache --bloodhound" in plain   # nxc line


async def test_build_short_command_stays_compact(app):
    """A short command must not inflate the preview box — it should shrink to the
    content it needs (regression: VerticalScroll wrapper filled to max-height)."""
    from pathlib import Path
    from textual.containers import VerticalScroll
    from aliasr.tui.build_screen.build_screen import BuildScreen

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        screen = BuildScreen("Test", "ftp <ip>", Path("x.md"))
        await app.push_screen(screen)
        await pilot.pause()
        await pilot.pause()
        ps = screen.query_one("#preview-scroll", VerticalScroll)
        assert ps.region.height <= 2, "one-line command should not fill the preview cap"
        assert ps.max_scroll_y == 0, "short command should not need to scroll"


async def test_build_preview_shows_commands_not_separator(app):
    """A newline-separated multi-command cheat previews the commands themselves;
    the build-time separator machinery (the `s` function / banners) never shows."""
    from pathlib import Path
    from aliasr.tui.build_screen.build_screen import BuildScreen

    cmd = "rm /tmp/x\nnxc smb <ip>\ntee out"

    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        b = BuildScreen("Test", cmd, Path("x.md"))
        await app.push_screen(b)
        await pilot.pause()
        await pilot.pause()
        rendered = b._preview.render().plain
        assert "rm /tmp/x" in rendered and "tee out" in rendered
        assert "s(){" not in rendered and "===" not in rendered


async def test_build_submit_assembles_multi_command(app):
    """Submitting a newline-separated multi-command cheat yields an assembled
    command: the `s` separator is defined, each step is announced with its
    (value-substituted) text, and the whole thing runs in bash."""
    import subprocess
    from pathlib import Path
    from aliasr.tui.build_screen.build_screen import BuildScreen

    captured = {}
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        b = BuildScreen("T", "echo one <ip>\necho two", Path("x.md"))
        await app.push_screen(b, lambda r: captured.__setitem__("cmd", r))
        await pilot.pause()
        await pilot.pause()
        b._exp_prefix = False
        b._exp_krb = False
        b._values["ip"] = "10.0.0.5"
        b.action_submit()
        await pilot.pause()

    final = captured["cmd"]
    assert "s(){" in final
    assert "s 'echo one 10.0.0.5'; echo one 10.0.0.5" in final
    r = subprocess.run(["bash", "-c", final], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "one 10.0.0.5" in r.stdout and "two" in r.stdout


async def test_build_faketime_tag_wraps_each_command_not_the_banner(app):
    """A #faketime cheat wraps each executed command in the skewrun guard
    (keyed off $FAKETIME, targeting the resolved <ip>), but the `=== <cmd> ===`
    banners still announce the bare command -- the wrapper never appears there."""
    from pathlib import Path
    from aliasr.tui.build_screen.build_screen import BuildScreen

    captured = {}
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        b = BuildScreen("T", "nxc smb <ip> -k\ncertipy find <ip> -k", Path("x.md"),
                        tags=frozenset({"faketime"}))
        await app.push_screen(b, lambda r: captured.__setitem__("cmd", r))
        await pilot.pause()
        await pilot.pause()
        b._exp_prefix = False
        b._exp_krb = False
        b._values["ip"] = "10.0.0.5"
        b.action_submit()
        await pilot.pause()

    final = captured["cmd"]
    # each executed command is guarded and routed through skewrun <ip> when unskewed
    assert 'if [ -n "$FAKETIME" ]; then nxc smb 10.0.0.5 -k; else' in final
    assert "skewrun 10.0.0.5 -- sh -c " in final
    # banners announce the bare commands; none announces the skewrun wrapper
    assert "s 'nxc smb 10.0.0.5 -k'" in final
    assert "s 'certipy find 10.0.0.5 -k'" in final
    assert "s 'skewrun" not in final


async def test_build_submit_ps_encode_skips_bash_separator(app):
    """A ps_encode (PowerShell) cheat must NOT get the bash `s` separator."""
    from pathlib import Path
    from aliasr.tui.build_screen.build_screen import BuildScreen

    captured = {}
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        b = BuildScreen("T", "Get-Thing\nGet-Other", Path("x.md"),
                        tags=frozenset({"ps_encode"}))
        await app.push_screen(b, lambda r: captured.__setitem__("cmd", r))
        await pilot.pause()
        await pilot.pause()
        b._exp_prefix = False
        b._exp_krb = False
        b.action_submit()
        await pilot.pause()

    final = captured["cmd"]
    assert final.startswith("powershell -e ")
    assert "s(){" not in final


async def test_build_submit_prefix_multi_command_is_valid_shell(app):
    """Regression (code-review finding): aliasr_prefix on an assembled
    multi-command cheat must produce runnable shell, not 'prefix s(){...}'."""
    import subprocess
    from pathlib import Path
    from aliasr.tui.build_screen.build_screen import BuildScreen

    captured = {}
    async with app.run_test(size=(100, 40)) as pilot:
        await pilot.pause()
        b = BuildScreen("T", "echo a\necho b", Path("x.md"))
        await app.push_screen(b, lambda r: captured.__setitem__("cmd", r))
        await pilot.pause()
        await pilot.pause()
        b._exp_krb = False
        b._exp_prefix = True
        b._prefix_global = "env "  # 'env <cmd>' runs <cmd>; stands in for proxychains
        b.action_submit()
        await pilot.pause()

    final = captured["cmd"]
    assert final.startswith("s(){"), final  # prefix did not corrupt the leading def
    r = subprocess.run(["bash", "-c", final], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "a" in r.stdout and "b" in r.stdout


async def test_preview_scroll_keybindings(app):
    """ctrl+up/down scroll the preview one line; ctrl+pageup/pagedown by a page,
    in both the build and variations screens."""
    from pathlib import Path
    from aliasr.tui.build_screen.build_screen import BuildScreen
    from aliasr.tui.build_screen.variations_screen import VariationsScreen
    from aliasr.core.variations import Variation

    long_cmd = "\n".join(f"echo step{i} <ip>" for i in range(30))

    async def drive(screen):
        await app.push_screen(screen)
        await pilot.pause()
        await pilot.pause()
        ps = screen.query_one("#preview-scroll")
        assert ps.max_scroll_y > 0
        await pilot.press("ctrl+down")
        await pilot.pause()
        one = ps.scroll_offset.y
        assert one == 1
        await pilot.press("ctrl+pagedown")
        await pilot.pause()
        assert ps.scroll_offset.y > one          # page moved further
        await pilot.press("ctrl+up")
        await pilot.pause()
        page = ps.scroll_offset.y
        await pilot.press("ctrl+pageup")
        await pilot.pause()
        assert ps.scroll_offset.y < page          # paged back up
        await app.pop_screen()
        await pilot.pause()

    async with app.run_test(size=(90, 20)) as pilot:
        await pilot.pause()
        await drive(BuildScreen("T", long_cmd, Path("x.md")))
        await drive(
            VariationsScreen(long_cmd, {"ip": [Variation("h", "1.1.1.1", "ip", "")]})
        )


async def test_cred_editor_autofills_nt_hash(app):
    """Typing a password in the editor auto-fills the NT hash field (CREDS_AUTO_HASH).

    Regression guard: the hash was silently blank because hashlib lacked md4.
    """
    from aliasr.tui.creds_screen.cred_editor import CredEditor

    async with app.run_test() as pilot:
        await pilot.pause()
        await app.push_screen(CredEditor("admin", "", "", "corp.local"))
        await pilot.pause()
        editor = app.screen
        assert isinstance(editor, CredEditor)
        editor.query_one("#password", Input).focus()
        await pilot.pause()
        await pilot.press("p", "a", "s", "s", "w", "o", "r", "d")
        await pilot.pause()
        assert (
            editor.query_one("#nt-hash", Input).value
            == "8846F7EAEE8FB117AD06BDD830B7586C"
        )
