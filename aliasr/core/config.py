import os
import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


# ---------- Models ----------


@dataclass(frozen=True)
class CheatsConf:
    paths: tuple[str, ...]
    exclude: tuple[str, ...]
    include_defaults: bool
    custom_first: bool
    default_grouping: str


@dataclass(frozen=True)
class GlobalsConf:
    path: str
    history: bool
    max_len: int
    show_grid: bool
    auto_krb: bool
    rows: int
    columns: int
    defaults: dict[str, str | list[str]]


@dataclass(frozen=True)
class CredsConf:
    kdbx: str
    key: str
    mask: bool
    auto_hash: bool


@dataclass(frozen=True)
class BuildConf:
    focus: str
    columns: int
    column_min_width: int


@dataclass(frozen=True)
class RignoreConf:
    """Configuration for rignore file tree walker.

    Controls ignore patterns, depth limits, and file filtering behavior
    when scanning directories. All fields default to None, which uses
    rignore's library defaults.
    """
    ignore_hidden: bool | None
    read_ignore_files: bool | None
    read_parents_ignores: bool | None
    read_git_ignore: bool | None
    read_global_git_ignore: bool | None
    read_git_exclude: bool | None
    require_git: bool | None
    additional_ignores: list[str] | None
    additional_ignore_paths: list[str] | None
    overrides: list[str] | None
    max_depth: int | None
    max_filesize: int | None
    follow_links: bool | None
    case_insensitive: bool | None
    same_file_system: bool | None


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
class Config:
    cheats: CheatsConf
    globals: GlobalsConf
    creds: CredsConf
    build: BuildConf
    rignore: RignoreConf
    keybindings: KeyBindingsConf
    theme: ThemeConf


# ---------- IO ----------


def _load_defaults() -> dict[str | None]:
    with (files("aliasr") / "data" / "config.toml").open("rb") as f:
        return tomllib.load(f)


def _load_user_toml() -> dict[str | None]:
    env = os.getenv("ALIASR_CONFIG")
    if env:
        p = Path(os.path.expanduser(env))
        p = p / "config.toml" if p.is_dir() else p
        if p.is_file():
            with p.open("rb") as f:
                return tomllib.load(f)
    xdg_base = Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config")
    for p in (
        xdg_base / "aliasr" / "config.toml",
        Path.home() / ".config" / "aliasr" / "config.toml",
    ):
        if p.is_file():
            with p.open("rb") as f:
                return tomllib.load(f)
    return {}


def _deep_update(
    base: dict[str | None], override: dict[str | None]
) -> dict[str | None]:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_update(out[k], v)
        else:
            out[k] = v
    return out


# ---------- Build ----------


def _build_config() -> Config:
    defaults = _load_defaults()
    user = _load_user_toml()
    merged = _deep_update(defaults, user)

    cheats_raw = dict(merged["cheats"])
    pkg_cheats_path = Path(files("aliasr") / "data" / "cheats")
    user_paths = [Path(p).expanduser() for p in cheats_raw["paths"] if p]
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
    # Check if user provided their own defaults
    if "globals" in user and "defaults" in user["globals"]:
        # User provided defaults - use ONLY those (no merge)
        for k, v in user["globals"]["defaults"].items():
            if isinstance(v, list):
                defaults_dict[k] = [str(item) for item in v]
            else:
                defaults_dict[k] = str(v)
    else:
        # No user defaults - use the built-in defaults
        if "defaults" in g_conf_raw:
            for k, v in g_conf_raw["defaults"].items():
                if isinstance(v, list):
                    defaults_dict[k] = [str(item) for item in v]
                else:
                    defaults_dict[k] = str(v)

    g_layout_raw = dict(g_conf_raw["layout"])
    g_conf = GlobalsConf(
        path=os.path.expanduser(g_conf_raw["path"]),
        history=bool(g_conf_raw["history"]),
        max_len=int(g_conf_raw["max_len"]),
        show_grid=bool(g_conf_raw["show_grid"]),
        auto_krb=bool(g_conf_raw["auto_krb"]),
        rows=int(g_layout_raw["rows"]),
        columns=int(g_layout_raw["columns"]),
        defaults=defaults_dict,
    )

    cr_raw = dict(merged["creds"])
    cr_conf = CredsConf(
        kdbx=os.path.expanduser(cr_raw["kdbx"]),
        key=os.path.expanduser(cr_raw["key"]),
        mask=bool(cr_raw["mask"]),
        auto_hash=bool(cr_raw["auto_hash"]),
    )

    build_raw = dict(merged["build"])
    build_layout_raw = dict(build_raw["layout"])
    build_conf = BuildConf(
        focus=str(build_raw["focus"]),
        columns=int(build_layout_raw["columns"]),
        column_min_width=int(build_layout_raw["column_min_width"]),
    )

    rignore_raw = dict(merged["rignore"])
    # Map 0 to None for unlimited depth/filesize
    max_depth = rignore_raw.get("max_depth")
    max_depth = None if max_depth == 0 else max_depth
    max_filesize = rignore_raw.get("max_filesize")
    max_filesize = None if max_filesize == 0 else max_filesize

    rignore_conf = RignoreConf(
        ignore_hidden=rignore_raw.get("ignore_hidden"),
        read_ignore_files=rignore_raw.get("read_ignore_files"),
        read_parents_ignores=rignore_raw.get("read_parents_ignores"),
        read_git_ignore=rignore_raw.get("read_git_ignore"),
        read_global_git_ignore=rignore_raw.get("read_global_git_ignore"),
        read_git_exclude=rignore_raw.get("read_git_exclude"),
        require_git=rignore_raw.get("require_git"),
        additional_ignores=rignore_raw.get("additional_ignores"),
        additional_ignore_paths=rignore_raw.get("additional_ignore_paths"),
        overrides=rignore_raw.get("overrides"),
        max_depth=max_depth,
        max_filesize=max_filesize,
        follow_links=rignore_raw.get("follow_links"),
        case_insensitive=rignore_raw.get("case_insensitive"),
        same_file_system=rignore_raw.get("same_file_system"),
    )

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

    return Config(
        cheats=cheats_conf,
        globals=g_conf,
        creds=cr_conf,
        build=build_conf,
        rignore=rignore_conf,
        keybindings=kb_conf,
        theme=theme_conf,
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
GLOBALS_ROWS: int = CONFIG.globals.rows
GLOBALS_COLUMNS: int = CONFIG.globals.columns
DEFAULT_GLOBALS: dict[str, str | list[str]] = CONFIG.globals.defaults

CREDS_KDBX: Path = Path(CONFIG.creds.kdbx)
CREDS_KEY: Path = Path(CONFIG.creds.key)
CREDS_MASK: bool = CONFIG.creds.mask
CREDS_AUTO_HASH: bool = CONFIG.creds.auto_hash

RIGNORE: RignoreConf = CONFIG.rignore

BUILD_COLUMNS: int = CONFIG.build.columns
BUILD_COLUMN_MIN_WIDTH: int = CONFIG.build.column_min_width
BUILD_FOCUS: str = CONFIG.build.focus

THEME: ThemeConf = CONFIG.theme
