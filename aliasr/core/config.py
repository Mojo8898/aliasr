import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------- Models ----------


@dataclass(frozen=True)
class CheatsConf:
    paths: tuple[Path, ...]
    exclude: tuple[str, ...]
    include_defaults: bool
    custom_first: bool
    default_grouping: str


@dataclass(frozen=True)
class GlobalsConf:
    path: Path
    history: bool
    max_len: int
    show_grid: bool
    auto_krb: bool
    defaults: dict[str, str | list[str]]


@dataclass(frozen=True)
class CredsConf:
    db: Path
    profile: Path | None
    mask: bool
    auto_hash: bool
    confirm_delete: bool


@dataclass(frozen=True)
class NxcConf:
    block_bulk_delete: bool


@dataclass(frozen=True)
class KeyBindingsConf:
    root: dict[str, str]
    build_screen: dict[str, str]
    grid_nav: dict[str, str]
    table: dict[str, str]
    table_copy: dict[str, str]


@dataclass(frozen=True)
class ThemeConf:
    name: str | None
    primary: str
    secondary: str
    accent: str
    foreground: str
    background: str
    success: str
    warning: str
    error: str
    surface: str
    panel: str
    dark: bool
    footer_key_foreground: str


@dataclass(frozen=True)
class BuildConf:
    separator: str


@dataclass(frozen=True)
class Config:
    cheats: CheatsConf
    globals: GlobalsConf
    creds: CredsConf
    nxc: NxcConf
    keybindings: KeyBindingsConf
    layout: dict[str, int]
    theme: ThemeConf
    build: BuildConf


# ---------- Helpers ----------


# The installed package dir. Plain path math instead of importlib.resources,
# whose import (+ zipfile) costs ~9 ms of startup for a package that's always on disk.
PKG_DIR: Path = Path(__file__).parent.parent


def _expand_path(p: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(p)))


def _aliasr_home() -> Path:
    return _expand_path(os.getenv("ALIASR_HOME") or "~/.aliasr")


ALIASR_HOME: Path = _aliasr_home()


def _resolve_under_home(value: str) -> Path:
    """Resolve a config path; bare/relative values live under ALIASR_HOME."""
    p = _expand_path(value)
    return p if p.is_absolute() else ALIASR_HOME / p


def _resolve_creds_db(value: str) -> Path:
    """Credentials DB path, with an ALIASR_CREDS_DB env override (tests/CI)."""
    env = os.getenv("ALIASR_CREDS_DB")
    return _expand_path(env) if env else _resolve_under_home(value)


def _resolve_profile(value: str) -> Path:
    """Exegol-history profile.sh path. Resolution order: ALIASR_PROFILE env, an
    explicit [creds].profile, exegol's own ~/.exegol_history/config.toml, then
    exegol's packaged default."""
    env = os.getenv("ALIASR_PROFILE")
    if env:
        return _expand_path(env)
    if value:
        return _expand_path(value)
    exegol_cfg = _expand_path("~/.exegol_history/config.toml")
    try:
        with exegol_cfg.open("rb") as f:
            p = tomllib.load(f).get("paths", {}).get("profile_sh_path")
        if p:
            return _expand_path(p)
    except OSError:
        pass
    return Path("/opt/tools/Exegol-history/profile.sh")


def _ensure_user_env() -> None:
    """First-run setup for the ~/.aliasr home: create it, drop an editable copy
    of the packaged config, and migrate the legacy ~/.aliasr.json globals file."""
    try:
        ALIASR_HOME.mkdir(parents=True, exist_ok=True)
    except OSError:
        return

    # Materialize an editable copy of the packaged defaults (never clobber).
    if not os.getenv("ALIASR_CONFIG"):
        target = ALIASR_HOME / "config.toml"
        if not target.exists():
            try:
                # Drop the packaged file's leading comment block (the
                # "edit the user copy instead" banner): this IS that copy, and
                # being merged over the defaults it needn't keep every value.
                src = (PKG_DIR / "data" / "config.toml").read_text(encoding="utf-8")
                lines = src.splitlines(keepends=True)
                i = 0
                while i < len(lines) and lines[i].lstrip().startswith("#"):
                    i += 1
                target.write_text("".join(lines[i:]), encoding="utf-8")
            except OSError:
                pass

    # Migrate the pre-reorg globals file. Only for the default home, so a custom
    # ALIASR_HOME (tests, CI) never moves a real user's ~/.aliasr.json.
    if not os.getenv("ALIASR_HOME"):
        new_globals = ALIASR_HOME / "globals.json"
        legacy = _expand_path("~/.aliasr.json")
        if not new_globals.exists() and legacy.is_file():
            try:
                legacy.replace(new_globals)
            except OSError:
                pass


def _deep_update(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_update(out[k], v)
        else:
            out[k] = v
    return out


# ---------- IO ----------


def _load_defaults() -> dict[str, Any]:
    with (PKG_DIR / "data" / "config.toml").open("rb") as f:
        return tomllib.load(f)


def _active_user_config_path() -> Path | None:
    """The config.toml actually in effect, by the same precedence used to load it.

    1. ``ALIASR_CONFIG`` (explicit file, or a dir holding config.toml)
    2. ``ALIASR_HOME``/config.toml
    3. ``XDG_CONFIG_HOME``/aliasr/config.toml
    4. ~/.config/aliasr/config.toml
    """
    env = os.getenv("ALIASR_CONFIG")
    if env:
        p = _expand_path(env)
        p = p / "config.toml" if p.is_dir() else p
        if p.is_file():
            return p

    xdg_base = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config")
    for p in (
        ALIASR_HOME / "config.toml",
        xdg_base / "aliasr" / "config.toml",
        Path.home() / ".config" / "aliasr" / "config.toml",
    ):
        if p.is_file():
            return p
    return None


def _load_user_toml() -> dict[str, Any]:
    p = _active_user_config_path()
    if p is None:
        return {}
    with p.open("rb") as f:
        return tomllib.load(f)


# ---------- Build ----------


def _build_config() -> Config:
    _ensure_user_env()
    defaults = _load_defaults()
    user = _load_user_toml()
    merged = _deep_update(defaults, user)

    cheats_raw = dict(merged["cheats"])
    user_paths = [_expand_path(p) for p in cheats_raw["paths"] if p]

    pkg_cheats_path = PKG_DIR / "data" / "cheats"
    if cheats_raw["include_defaults"]:
        if cheats_raw["custom_first"]:
            base: list[Path] = [*user_paths, pkg_cheats_path]
        else:
            base = [pkg_cheats_path, *user_paths]
    else:
        base = [*user_paths]

    seen = set()
    cheats_paths = [
        p for p in base if (str_p := str(p)) not in seen and not seen.add(str_p)
    ]

    cheats_conf = CheatsConf(
        paths=tuple(cheats_paths),
        exclude=tuple(cheats_raw["exclude"]),
        include_defaults=bool(cheats_raw["include_defaults"]),
        custom_first=bool(cheats_raw["custom_first"]),
        default_grouping=cheats_raw["default_grouping"],
    )

    g_conf_raw = dict(merged["globals"])
    defaults_dict = {}

    if "globals" in user and isinstance(user["globals"], dict) and "defaults" in user["globals"]:
        for k, v in user["globals"]["defaults"].items():
            defaults_dict[k] = [str(i) for i in v] if isinstance(v, list) else str(v)
    else:
        if "defaults" in g_conf_raw:
            for k, v in g_conf_raw["defaults"].items():
                defaults_dict[k] = [str(i) for i in v] if isinstance(v, list) else str(v)

    g_conf = GlobalsConf(
        path=_resolve_under_home(str(g_conf_raw["path"])),
        history=bool(g_conf_raw["history"]),
        max_len=int(g_conf_raw["max_len"]),
        show_grid=bool(g_conf_raw["show_grid"]),
        auto_krb=bool(g_conf_raw["auto_krb"]),
        defaults=defaults_dict,
    )

    cr_raw = dict(merged["creds"])
    cr_conf = CredsConf(
        db=_resolve_creds_db(str(cr_raw["db"])),
        profile=_resolve_profile(str(cr_raw.get("profile", "") or "")),
        mask=bool(cr_raw["mask"]),
        auto_hash=bool(cr_raw["auto_hash"]),
        confirm_delete=bool(cr_raw["confirm_delete"]),
    )

    nxc_raw = dict(merged["nxc"])
    nxc_conf = NxcConf(block_bulk_delete=bool(nxc_raw["block_bulk_delete"]))

    kb_raw = dict(merged["keybindings"])
    table = dict(kb_raw.get("table", {}))
    table_copy = table.pop("copy", {})

    kb_conf = KeyBindingsConf(
        root={k: v for k, v in kb_raw.items() if not isinstance(v, dict)},
        build_screen=kb_raw.get("build_screen", {}),
        grid_nav=kb_raw.get("grid_nav", {}),
        table=table,
        table_copy=table_copy,
    )

    theme_raw = dict(merged["theme"])
    theme_conf = ThemeConf(
        name=theme_raw.get("name"),
        primary=theme_raw["primary"],
        secondary=theme_raw["secondary"],
        accent=theme_raw["accent"],
        foreground=theme_raw["foreground"],
        background=theme_raw["background"],
        success=theme_raw["success"],
        warning=theme_raw["warning"],
        error=theme_raw["error"],
        surface=theme_raw["surface"],
        panel=theme_raw["panel"],
        dark=bool(theme_raw["dark"]),
        footer_key_foreground=theme_raw["footer_key_foreground"],
    )

    build_conf = BuildConf(separator=str(merged["build"]["separator"]))

    layout_dict = {k: int(v) for k, v in merged["layout"].items()}

    return Config(
        cheats=cheats_conf,
        globals=g_conf,
        creds=cr_conf,
        nxc=nxc_conf,
        keybindings=kb_conf,
        layout=layout_dict,
        theme=theme_conf,
        build=build_conf,
    )


CONFIG: Config = _build_config()


# ---------- Keybinding Accessors ----------


def kb_root(name: str) -> str:
    return CONFIG.keybindings.root[name]


def kb_build_screen(name: str) -> str:
    return CONFIG.keybindings.build_screen[name]


def kb_grid_nav(name: str) -> str:
    return CONFIG.keybindings.grid_nav[name]


def kb_table(name: str) -> str:
    return CONFIG.keybindings.table[name]


def kb_table_copy(name: str) -> str:
    return CONFIG.keybindings.table_copy[name]


# ---------- Convenience Exports ----------


CHEAT_PATHS: tuple[Path, ...] = CONFIG.cheats.paths
CHEATS_EXCLUDE: tuple[str, ...] = CONFIG.cheats.exclude
CHEATS_DEFAULT_GROUPING: str = CONFIG.cheats.default_grouping

GLOBALS_FILE: Path = Path(CONFIG.globals.path)
GLOBALS_SHOW_GRID: bool = CONFIG.globals.show_grid
GLOBALS_HISTORY: bool = CONFIG.globals.history
GLOBALS_MAX_LEN: int = CONFIG.globals.max_len
GLOBALS_AUTO_KRB: bool = CONFIG.globals.auto_krb
DEFAULT_GLOBALS: dict[str, str | list[str]] = CONFIG.globals.defaults

CREDS_DB: Path = Path(CONFIG.creds.db)
CREDS_PROFILE: Path | None = CONFIG.creds.profile
CREDS_MASK: bool = CONFIG.creds.mask
CREDS_AUTO_HASH: bool = CONFIG.creds.auto_hash
CREDS_CONFIRM_DELETE: bool = CONFIG.creds.confirm_delete

NXC_BLOCK_BULK_DELETE: bool = CONFIG.nxc.block_bulk_delete

GLOBALS_ROWS: int = CONFIG.layout["globals_rows"]
GLOBALS_COLUMNS: int = CONFIG.layout["globals_columns"]
BUILD_COLUMNS: int = CONFIG.layout["build_columns"]

THEME: ThemeConf = CONFIG.theme
BUILD_SEPARATOR: str = CONFIG.build.separator


# ---------- Config staleness (missing default declarations) ----------

# Subtrees whose children are user-populated, not schema — don't flag their
# individual keys as "missing" (e.g. a user's own set of global defaults).
_FREEFORM_SUBTREES: frozenset[str] = frozenset({"globals.defaults"})


def _missing_default_keys(
    defaults: dict[str, Any], user: dict[str, Any], prefix: str = ""
) -> list[str]:
    """Dotted keys present in `defaults` but absent from `user`, recursively.

    Recurses into nested tables (so a newly added option inside an existing
    section is caught) but treats the free-form subtrees as opaque.
    """
    missing: list[str] = []
    for key, dval in defaults.items():
        path = prefix + key
        if key not in user:
            missing.append(path)
            continue
        if (
            isinstance(dval, dict)
            and isinstance(user[key], dict)
            and path not in _FREEFORM_SUBTREES
        ):
            missing.extend(_missing_default_keys(dval, user[key], path + "."))
    return missing


def stale_config() -> tuple[Path, list[str]] | None:
    """Return (path, missing_keys) when the in-use config.toml predates the
    current defaults (i.e. is missing option declarations), else ``None``.

    Cheap: parses the two small TOML files and walks the keys. Values the user
    has customised are ignored — only absent declarations count.
    """
    path = _active_user_config_path()
    if path is None:
        return None
    try:
        with path.open("rb") as f:
            user = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    missing = _missing_default_keys(_load_defaults(), user)
    return (path, missing) if missing else None


def migrate_config(path: Path) -> Path:
    """Back up `path` to ``<name>.bak`` and write the current packaged defaults.

    Returns the backup path. The packaged file's leading comment banner is
    dropped (as first-run setup does), since this is the editable user copy.
    """
    src = (PKG_DIR / "data" / "config.toml").read_text(encoding="utf-8")
    lines = src.splitlines(keepends=True)
    i = 0
    while i < len(lines) and lines[i].lstrip().startswith("#"):
        i += 1

    bak = path.with_name(path.name + ".bak")
    path.replace(bak)  # move the old config aside first
    path.write_text("".join(lines[i:]), encoding="utf-8")
    return bak
