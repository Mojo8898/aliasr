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

    # A bundled cheat file that defines references for <working_dir>, so the
    # param screen has options and stays open.
    md = Path(next(c.path for c in app.cheats if c.path.endswith("linux/linux_privesc.md")))
    async with app.run_test(size=(160, 45)) as pilot:
        await pilot.pause()
        await app.push_screen(BuildScreen("t", "cd <working_dir>", md))
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
        assert build._values["working_dir"] == "/tmp"
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
