"""Config staleness detection + in-place injection of missing defaults."""
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


# ---------- inject_missing_defaults ----------


def test_inject_adds_key_in_existing_section(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[creds]\nmask = false\n")
    config.inject_missing_defaults(cfg, ["creds.confirm_delete"])
    with cfg.open("rb") as f:
        data = tomllib.load(f)
    assert data["creds"]["confirm_delete"] is True  # default injected
    assert data["creds"]["mask"] is False            # existing value preserved


def test_inject_adds_missing_section(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[creds]\nmask = false\n")
    config.inject_missing_defaults(cfg, ["nxc"])
    with cfg.open("rb") as f:
        data = tomllib.load(f)
    assert data["nxc"]["block_bulk_delete"] is False
    assert data["creds"]["mask"] is False


def test_inject_preserves_comments(tmp_path):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[creds]\n# keep me\nmask = false\n")
    config.inject_missing_defaults(cfg, ["creds.confirm_delete"])
    assert "# keep me" in cfg.read_text()


def test_inject_resolves_all_drift_and_keeps_values(tmp_path, monkeypatch):
    # A near-empty config is missing almost everything; injecting the full set
    # must yield a valid, drift-free file with the user's value preserved.
    cfg = tmp_path / "config.toml"
    cfg.write_text("[creds]\nmask = true\n")
    monkeypatch.setenv("ALIASR_CONFIG", str(cfg))

    stale = config.stale_config()
    assert stale is not None
    config.inject_missing_defaults(cfg, stale[1])

    with cfg.open("rb") as f:  # must still parse
        data = tomllib.load(f)
    assert config._missing_default_keys(config._load_defaults(), data) == []
    assert data["creds"]["mask"] is True  # preserved


def test_update_stale_config_injects_and_silences(tmp_path, monkeypatch, capsys):
    from aliasr import __main__ as m

    cfg = tmp_path / "config.toml"
    cfg.write_text("[creds]\nmask = false\n\n[nxc]\n")
    monkeypatch.setenv("ALIASR_CONFIG", str(cfg))

    m._update_stale_config()
    out = capsys.readouterr().out
    assert "missing" in out and "updated" in out
    with cfg.open("rb") as f:
        assert tomllib.load(f)["creds"]["confirm_delete"] is True

    assert config.stale_config() is None  # no longer stale -> won't recur
