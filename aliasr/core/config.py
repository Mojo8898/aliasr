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
    defaults: dict[str, str | list[str]]


@dataclass(frozen=True)
class CredsConf:
    kdbx: str
    key: str
    mask: bool
    auto_hash: bool


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
    keybindings: KeyBindingsConf
    layout: dict[str, int]
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

    g_conf = GlobalsConf(
        path=os.path.expanduser(g_conf_raw["path"]),
        history=bool(g_conf_raw["history"]),
        max_len=int(g_conf_raw["max_len"]),
        show_grid=bool(g_conf_raw["show_grid"]),
        auto_krb=bool(g_conf_raw["auto_krb"]),
        defaults=defaults_dict,
    )

    cr_raw = dict(merged["creds"])
    cr_conf = CredsConf(
        kdbx=os.path.expanduser(cr_raw["kdbx"]),
        key=os.path.expanduser(cr_raw["key"]),
        mask=bool(cr_raw["mask"]),
        auto_hash=bool(cr_raw["auto_hash"]),
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

    layout_dict = {k: int(v) for k, v in merged["layout"].items()}

    return Config(
        cheats=cheats_conf,
        globals=g_conf,
        creds=cr_conf,
        keybindings=kb_conf,
        layout=layout_dict,
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
DEFAULT_GLOBALS: dict[str, str | list[str]] = CONFIG.globals.defaults

CREDS_KDBX: Path = Path(CONFIG.creds.kdbx)
CREDS_KEY: Path = Path(CONFIG.creds.key)
CREDS_MASK: bool = CONFIG.creds.mask
CREDS_AUTO_HASH: bool = CONFIG.creds.auto_hash

GLOBALS_ROWS: int = CONFIG.layout["globals_rows"]
GLOBALS_COLUMNS: int = CONFIG.layout["globals_columns"]
BUILD_COLUMNS: int = CONFIG.layout["build_columns"]

THEME: ThemeConf = CONFIG.theme
