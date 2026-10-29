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


async def test_theme_applied_without_css_refresh(app, monkeypatch):
    """The configured theme is live from the first frame, with no re-parse.

    Aliasr sets the theme before Textual's first CSS parse; assigning it after
    mount would trigger refresh_css (a full re-parse + restyle) on every launch.
    """
    from textual.color import Color

    from aliasr.core.config import THEME

    refreshes = []
    monkeypatch.setattr(app, "refresh_css", lambda *a, **k: refreshes.append(1))
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == THEME.name
        assert app.has_class(f"-theme-{THEME.name}")
        bg = Color.parse(app.current_theme.background)
        assert app.screen.styles.background == bg
        assert not refreshes, "theme change re-parsed CSS during startup"


async def test_footer_keys_skip_compact_toggle(app, monkeypatch):
    """Footer keys mount with Footer.compact preset, styled as before.

    aliasr's Footer presets FooterKey.compact so the key watcher never fires
    (it used to add then remove -compact, restyling every key twice).
    """
    from textual.widgets._footer import FooterKey

    from aliasr.tui.utils.footer import Footer

    # data_bind always re-runs the watcher; only a real class flip costs a restyle
    toggles = []
    orig = FooterKey._watch_compact

    def watch(self, compact):
        if (
            not self.has_class("-command-palette")
            and self.has_class("-compact") != compact
        ):
            toggles.append(compact)
        orig(self, compact)

    monkeypatch.setattr(FooterKey, "_watch_compact", watch)
    async with app.run_test() as pilot:
        await pilot.pause()
        footer = app.screen.query_one(Footer)
        keys = [
            k for k in footer.query(FooterKey) if not k.has_class("-command-palette")
        ]
        assert keys, "footer rendered no binding keys"
        assert all(k.compact == footer.compact for k in keys)
        assert not any(k.has_class("-compact") for k in keys)
        assert all(k.size.width > 0 for k in keys)  # laid out and visible
        assert not toggles, f"bound keys flipped -compact (extra restyles): {toggles}"


async def test_quit_binding(app):
    """Ctrl+Q exits cleanly (safe_exit action wired up)."""
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+q")
        await pilot.pause()
    # Context manager exiting without error means the app shut down cleanly.
