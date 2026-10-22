"""Shared fixtures for the Pilot-driven TUI tests."""

import pytest

from aliasr.app import Aliasr
from aliasr.core.bootstrap import launch_app


@pytest.fixture
def app() -> Aliasr:
    """A fully-configured app, built via the real startup path.

    Mirrors what ``aliasr`` does on launch (cheats + globals loaded), but with
    tmux integration disabled so tests are environment-independent.
    """
    return launch_app(execute=False, pane=None, previous=False)
