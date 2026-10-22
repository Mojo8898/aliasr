"""Shared fixtures for the Pilot-driven TUI tests."""

import os
import tempfile
from pathlib import Path

# Isolate all on-disk state (config, globals, creds DB) into a throwaway dir
# BEFORE importing aliasr, so tests never touch the developer's real ~/.aliasr
# or the shared Exegol-history database. config.CONFIG is built at import time,
# so these env vars must be set first.
_TEST_HOME = Path(tempfile.mkdtemp(prefix="aliasr-test-"))
os.environ.setdefault("ALIASR_HOME", str(_TEST_HOME))
os.environ.setdefault("ALIASR_CREDS_DB", str(_TEST_HOME / "exh.db"))
os.environ.setdefault("ALIASR_PROFILE", str(_TEST_HOME / "profile.sh"))

import pytest  # noqa: E402

from aliasr.app import Aliasr  # noqa: E402
from aliasr.core.bootstrap import launch_app  # noqa: E402


@pytest.fixture
def app() -> Aliasr:
    """A fully-configured app, built via the real startup path.

    Mirrors what ``aliasr`` does on launch (cheats + globals loaded), but with
    tmux integration disabled so tests are environment-independent.
    """
    return launch_app(execute=False, pane=None, previous=False)
