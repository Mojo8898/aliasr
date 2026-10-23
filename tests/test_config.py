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
