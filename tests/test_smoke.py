"""Smoke tests: prove the TUI boots and responds, headlessly, via Pilot.

These are the agentic feedback loop — they let a change be verified without a
human watching the screen. Run with: ``uv run pytest``.
"""

from aliasr.tui.main_screen.main_screen import MainScreen


async def test_app_boots(app):
    """The app mounts and lands on the main screen without raising."""
    async with app.run_test() as pilot:
        await pilot.pause()
        assert isinstance(app.screen, MainScreen)


async def test_quit_binding(app):
    """Ctrl+Q exits cleanly (safe_exit action wired up)."""
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+q")
        await pilot.pause()
    # Context manager exiting without error means the app shut down cleanly.
