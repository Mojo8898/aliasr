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
