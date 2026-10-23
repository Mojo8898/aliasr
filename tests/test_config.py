"""Config staleness detection + migration (missing default declarations)."""
import tomllib

from aliasr.core import config


# ---------- key diffing ----------


def test_missing_default_keys_reports_nested():
    defaults = {"a": {"b": 1, "c": 2}, "d": 3}
    user = {"a": {"b": 1}}
    assert config._missing_default_keys(defaults, user) == ["a.c", "d"]


def test_missing_default_keys_ignores_freeform_globals_defaults():
    # A user's own global defaults must not be flagged as "missing" schema.
    defaults = {"globals": {"defaults": {"lhost": [""], "ip": [""]}}}
    user = {"globals": {"defaults": {"my_custom": ["x"]}}}
    assert config._missing_default_keys(defaults, user) == []


def test_missing_default_keys_none_when_complete():
    defaults = {"a": {"b": 1}}
    user = {"a": {"b": 99}}  # value differs, but the key is present
    assert config._missing_default_keys(defaults, user) == []


# ---------- stale_config ----------


def test_stale_config_flags_outdated(tmp_path, monkeypatch):
    # Sections exist but newer options inside them are absent.
    cfg = tmp_path / "config.toml"
    cfg.write_text("[creds]\nmask = false\n\n[nxc]\n")
    monkeypatch.setenv("ALIASR_CONFIG", str(cfg))

    stale = config.stale_config()
    assert stale is not None
    path, missing = stale
    assert path == cfg
    # Newly added options inside existing sections must be reported.
    assert "nxc.block_bulk_delete" in missing
    assert "creds.confirm_delete" in missing


def test_stale_config_none_for_current_defaults(tmp_path, monkeypatch):
    import shutil

    cfg = tmp_path / "config.toml"
    shutil.copy(config.PKG_DIR / "data" / "config.toml", cfg)
    monkeypatch.setenv("ALIASR_CONFIG", str(cfg))
    assert config.stale_config() is None


def test_stale_config_none_when_no_user_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ALIASR_CONFIG", str(tmp_path / "does-not-exist.toml"))
    # Falls through to the standard locations; the test home has a current copy.
    result = config.stale_config()
    assert result is None or result[1] == []


# ---------- migrate_config ----------


def test_migrate_config_backs_up_and_writes_defaults(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[creds]\nmask = true\n")

    bak = config.migrate_config(cfg)

    assert bak == tmp_path / "config.toml.bak"
    assert bak.read_text() == "[creds]\nmask = true\n"  # old config preserved verbatim

    with cfg.open("rb") as f:
        data = tomllib.load(f)
    # New file carries the current schema and no longer reads as stale.
    assert data["nxc"]["block_bulk_delete"] is False
    assert data["creds"]["confirm_delete"] is True
    assert config._missing_default_keys(config._load_defaults(), data) == []


# ---------- drift opt-out (ignore_drift) ----------


def test_missing_default_keys_skips_config_section():
    # The [config] section holds the drift controls; its absence isn't drift.
    defaults = {"config": {"ignore_drift": False}, "x": 1}
    assert config._missing_default_keys(defaults, {"x": 1}) == []


def test_ignore_drift_suppresses_stale(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[creds]\nmask = false\n\n[config]\nignore_drift = true\n")
    monkeypatch.setenv("ALIASR_CONFIG", str(cfg))
    # Missing plenty of keys, but opted out -> no prompt.
    assert config.stale_config() is None


def test_ignore_config_drift_appends_when_absent(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[creds]\nmask = false\n")
    config.ignore_config_drift(cfg)
    with cfg.open("rb") as f:
        assert tomllib.load(f)["config"]["ignore_drift"] is True
    # The pre-existing content is preserved.
    assert "[creds]" in cfg.read_text()


def test_ignore_config_drift_flips_existing(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[config]\nignore_drift = false\n")
    config.ignore_config_drift(cfg)
    with cfg.open("rb") as f:
        assert tomllib.load(f)["config"]["ignore_drift"] is True


def test_declining_persists_and_suppresses_future_prompts(tmp_path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[creds]\nmask = false\n\n[nxc]\n")
    monkeypatch.setenv("ALIASR_CONFIG", str(cfg))

    assert config.stale_config() is not None   # shown the first time
    config.ignore_config_drift(cfg)            # user declines -> persisted
    assert config.stale_config() is None       # never shown again


def test_prompt_stale_config_decline_opts_out(tmp_path, monkeypatch):
    """Declining the startup prompt persists ignore_drift and never re-prompts."""
    from aliasr import __main__ as m

    cfg = tmp_path / "config.toml"
    cfg.write_text("[creds]\nmask = false\n\n[nxc]\n")
    monkeypatch.setenv("ALIASR_CONFIG", str(cfg))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "n")

    m._prompt_stale_config()
    with cfg.open("rb") as f:
        assert tomllib.load(f)["config"]["ignore_drift"] is True

    # A second launch must not prompt again.
    def _boom(*_):
        raise AssertionError("prompted again after opting out")

    monkeypatch.setattr("builtins.input", _boom)
    m._prompt_stale_config()


def test_prompt_stale_config_enter_opts_out(tmp_path, monkeypatch):
    """Just pressing Enter at the drift prompt keeps the config and opts out."""
    from aliasr import __main__ as m

    cfg = tmp_path / "config.toml"
    cfg.write_text("[creds]\nmask = false\n\n[nxc]\n")
    monkeypatch.setenv("ALIASR_CONFIG", str(cfg))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "")  # Enter

    m._prompt_stale_config()
    with cfg.open("rb") as f:
        assert tomllib.load(f)["config"]["ignore_drift"] is True
