import json
import os
import re
from typing import Any

from aliasr.core.config import (
    DEFAULT_GLOBALS,
    GLOBALS_FILE,
    GLOBALS_HISTORY,
    GLOBALS_MAX_LEN,
)


_SEP_RE = re.compile(r"[-.\s]+")
_SAFE_RE = re.compile(r"[^a-z0-9_]")
_MULTI_RE = re.compile(r"_+")

_STATE_RAW: dict[str, list[str]] = {}
_LOADED = False
_LAST_SERIALIZED: str | None = None
_MAX_LEN = GLOBALS_MAX_LEN if GLOBALS_HISTORY else 1
_globals_bootstrapped = False


# ---------- Helpers ----------


def _as_list(value: Any, *, max_len: int | None = None) -> list[str]:
    """Convert any value to a normalized list of strings with deduplication."""
    if max_len is None:
        max_len = _MAX_LEN
    items = (
        [str(v).strip() for v in value]
        if isinstance(value, list)
        else [str(value).strip()]
        if value is not None
        else []
    )
    out, seen = [], set()
    for s in items:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    if items and items[0] == "":
        out = [""] + out
    return out[:max_len]


def _normalize_dict_keys(d: dict[str, Any]) -> dict[str, Any]:
    """Normalize all dictionary keys to valid identifiers."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        nk = normalize_key(k)
        if nk in out:
            i = 1
            while f"{nk}_{i}" in out:
                i += 1
            nk = f"{nk}_{i}"
        out[nk] = v
    return out


def _canonicalize(state: dict[str, Any]) -> dict[str, list[str]]:
    """Convert state to canonical form with normalized keys and list values."""
    canon: dict[str, list[str]] = {}
    for k, v in state.items():
        nk = normalize_key(str(k))
        if not nk:
            continue
        seq = v if isinstance(v, list) else [v]
        canon[nk] = _normalize_history_list(seq)
    return canon


def _normalize_history_list(values: list[str]) -> list[str]:
    """Normalize a history list: deduplicate, preserve empty leader, enforce max length."""
    items = [((v or "").strip()) for v in values]
    first_empty = bool(items and items[0] == "")
    out, seen = ([""] if first_empty else []), set()
    it = items[1:] if first_empty else items
    for s in it:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return (out or [""])[:_MAX_LEN]


# ---------- File I/O ----------


def _serialize(state: dict[str, list[str]]) -> str:
    """Serialize state to canonical JSON format."""
    return json.dumps(state, indent=4, ensure_ascii=False) + "\n"


def _atomic_write_text(path, text: str, encoding: str = "utf-8") -> None:
    """Write text to file atomically using temp file + rename."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, path)


def _persist_from_cache() -> None:
    """Write in-memory state to disk if changed."""
    global _LAST_SERIALIZED
    payload = _serialize(_STATE_RAW)
    if payload == _LAST_SERIALIZED:
        return
    _atomic_write_text(GLOBALS_FILE, payload)
    _LAST_SERIALIZED = payload


def _sync_env_to_global(env_name: str, global_name: str) -> None:
    """Sync an environment variable to a global if it differs from current value."""
    env_val = (os.environ.get(env_name) or "").strip()
    if env_val:
        cur = _STATE_RAW.get(global_name, [])
        if (cur[0] if cur else "") != env_val:
            _STATE_RAW[global_name] = _as_list([env_val, *cur])
            if not _STATE_RAW[global_name]:
                _STATE_RAW[global_name] = [""]
            _persist_from_cache()


# ---------- Initialization ----------


def _ensure_loaded() -> None:
    """Ensure globals are loaded into memory, creating defaults if needed."""
    global _LOADED, _STATE_RAW, _LAST_SERIALIZED
    if _LOADED:
        return
    if not GLOBALS_FILE.is_file():
        clear_globals()
        return
    try:
        raw_text = GLOBALS_FILE.read_text(encoding="utf-8")
        data = json.loads(raw_text)
        if not isinstance(data, dict) or not data:
            clear_globals()
            return

        had_multi_history = any(
            isinstance(v, list) and len([s for s in v if str(s).strip()]) > 1
            for v in data.values()
        )
        if had_multi_history and not GLOBALS_HISTORY:
            raise SystemExit(
                "Refusing to load globals: the globals file contains multi-value history entries "
                "but GLOBALS_HISTORY is disabled.\n"
                'To keep your history, set "globals_history = true" within your config.toml.\n'
            )
        canon = _canonicalize(_normalize_dict_keys(data))
        ser = _serialize(canon)
        if ser != raw_text:
            _atomic_write_text(GLOBALS_FILE, ser)
        _STATE_RAW = canon
        _LAST_SERIALIZED = ser
        _LOADED = True
    except json.JSONDecodeError as e:
        raise SystemExit(
            f"Error: Malformed JSON in {GLOBALS_FILE}\n{e}\n"
            "Fix or delete the file to reset values to defaults."
        )
    except Exception as e:
        raise SystemExit(f"Warning: error reading {GLOBALS_FILE}: {e}")


# ---------- Public API ----------


def normalize_key(key: str) -> str:
    """Normalize a key to a valid Python identifier."""
    if not key:
        return ""
    k = key.lower()
    k = _SEP_RE.sub("_", k)
    k = _SAFE_RE.sub("", k)
    k = _MULTI_RE.sub("_", k).strip("_")
    return k or "unnamed"


def load_globals() -> dict[str, str]:
    """Load current global values (first entry of each history list)."""
    global _globals_bootstrapped
    _ensure_loaded()

    if not _globals_bootstrapped:
        _globals_bootstrapped = True

        env_mappings = {
            "KRB5CCNAME": "krb5ccname",
            "ALIASR_PREFIX": "aliasr_prefix",
        }

        for env_name, global_name in env_mappings.items():
            _sync_env_to_global(env_name, global_name)

    return {k: (v[0] if v else "") for k, v in _STATE_RAW.items()}


def load_globals_raw() -> dict[str, list[str]]:
    """Get full history for all globals (used by UI components)."""
    _ensure_loaded()
    return _STATE_RAW


def save_global(key: str, value: str) -> None:
    """Save a single global value, prepending to history."""
    _ensure_loaded()
    nk = normalize_key(key)
    if not nk:
        return
    existing = _STATE_RAW.get(nk, [])
    seq = [value, *[x for x in existing if x != value]]
    _STATE_RAW[nk] = _normalize_history_list(seq)
    _persist_from_cache()


def save_globals(payload: dict[str, Any]) -> None:
    """Save multiple globals at once."""
    _ensure_loaded()
    for k, v in payload.items():
        nk = normalize_key(k)
        if not nk:
            continue
        seq = v if isinstance(v, list) else [v]
        _STATE_RAW[nk] = _normalize_history_list(seq)
    _persist_from_cache()


def save_globals_order(key_order: list[str]) -> None:
    """Reorder globals in file while preserving values."""
    _ensure_loaded()
    order = []
    seen = set()
    for k in key_order:
        nk = normalize_key(k)
        if nk and nk in _STATE_RAW and nk not in seen:
            seen.add(nk)
            order.append(nk)
    for k in list(_STATE_RAW.keys()):
        if k not in seen:
            order.append(k)
    vals = {k: _STATE_RAW[k] for k in _STATE_RAW.keys()}
    _STATE_RAW.clear()
    for k in order:
        _STATE_RAW[k] = _normalize_history_list(vals[k])
    _persist_from_cache()


def delete_globals(keys: list[str] | set[str]) -> None:
    """Delete one or more globals."""
    _ensure_loaded()
    removed = False
    for k in keys:
        nk = normalize_key(k)
        if nk in _STATE_RAW:
            _STATE_RAW.pop(nk)
            removed = True
    if removed:
        _persist_from_cache()


def get_history(key: str) -> list[str]:
    """Get history for a specific global (empty if history disabled)."""
    if not GLOBALS_HISTORY:
        return []
    _ensure_loaded()
    return _STATE_RAW.get(normalize_key(key), []) or []


def clear_globals() -> None:
    """Create default globals file with configured defaults."""
    global _STATE_RAW, _LAST_SERIALIZED, _LOADED
    seed: dict[str, Any] = {}
    # Include environment KRB5CCNAME if present
    env_krb = (os.environ.get("KRB5CCNAME") or "").strip()
    if env_krb:
        seed["krb5ccname"] = [env_krb]

    # Add configured defaults
    for k, v in DEFAULT_GLOBALS.items():
        nk = normalize_key(k)
        if nk:
            seed[nk] = v

    canon = _canonicalize(seed)
    text = _serialize(canon)
    _atomic_write_text(GLOBALS_FILE, text)
    _STATE_RAW = canon
    _LAST_SERIALIZED = text
    _LOADED = True
