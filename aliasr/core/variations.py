import re
import threading
import tomllib
from dataclasses import dataclass
from pathlib import Path

from aliasr.core.config import CHEAT_PATHS


@dataclass(frozen=True, slots=True)
class Variation:
    key: str
    value: str
    param: str
    command_prefix: str
    is_universal: bool = False


_VARS: dict[str, dict[str, dict[str, str]]] = {}
_UNIVERSAL_VARS: dict[str, dict[str, str]] = {}
_LOADED = False
_LOCK = threading.Lock()


# ---------- Internal ----------


def _head(cmd: str) -> str:
    return (cmd or "").split()[0] if cmd else ""


def _merge(dst, src) -> None:
    for cmd, params in src.items():
        # Handle universal variations (single underscore)
        if cmd == "_":
            for p, choices in (params or {}).items():
                _UNIVERSAL_VARS.setdefault(p, {}).update(choices or {})
        else:
            # Regular command-specific variations
            d_params = dst.setdefault(cmd, {})
            for p, choices in (params or {}).items():
                d_params.setdefault(p, {}).update(choices or {})


def _load_one(path: Path) -> dict[str, dict[str, dict[str, str]]]:
    with path.open("rb") as f:
        data = tomllib.load(f)

    result = {}
    for cmd, params in (data if isinstance(data, dict) else {}).items():
        if cmd == "_":
            # Store universal variations separately
            result["_"] = {
                str(param): (choices if isinstance(choices, dict) else {})
                for param, choices in (params if isinstance(params, dict) else {}).items()
            }
        else:
            # Regular command-specific variations
            result[str(cmd)] = {
                str(param): (choices if isinstance(choices, dict) else {})
                for param, choices in (params if isinstance(params, dict) else {}).items()
            }
    return result


# ---------- Public API ----------


def load_variations() -> None:
    """Load package defaults first, then overlay customs from CHEAT_PATHS."""
    global _VARS, _UNIVERSAL_VARS, _LOADED
    if _LOADED:
        return
    with _LOCK:
        if _LOADED:
            return

        tmp: dict[str, dict[str, dict[str, str]]] = {}
        _UNIVERSAL_VARS.clear()

        for path in CHEAT_PATHS:
            var_file = path / "variations.toml"
            if var_file.exists():
                _merge(tmp, _load_one(var_file))

        # Remove _ from regular vars if it ended up there
        tmp.pop("_", None)
        
        _VARS = tmp
        _LOADED = True


def get_all_variations(cmd: str, params: list[str]) -> dict[str, list[Variation]]:
    """Get variations for parameters, checking both command-specific and universal."""
    load_variations()
    head = _head(cmd)
    per_param = _VARS.get(head, {})
    
    result = {}
    for p in params:
        variations = []
        
        # First check command-specific variations (higher priority)
        if p in per_param:
            variations.extend([
                Variation(k, v, p, head, is_universal=False) 
                for k, v in per_param[p].items()
            ])
        
        # Then check universal variations (only if no command-specific)
        if not variations and p in _UNIVERSAL_VARS:
            variations.extend([
                Variation(k, v, p, "_", is_universal=True)
                for k, v in _UNIVERSAL_VARS[p].items()
            ])
        
        if variations:
            result[p] = variations
    
    return result


def is_variation_param(cmd: str, param: str) -> bool:
    """Check if a parameter has variations (command-specific or universal)."""
    load_variations()
    head = _head(cmd)
    
    # Check command-specific first
    if param in _VARS.get(head, {}):
        return True
    
    # Check universal
    return param in _UNIVERSAL_VARS


def apply_variation(cmd: str, param: str, value: str) -> str:
    return re.compile(rf"<{re.escape(param)}(?:\|[^>]*)?>").sub(value, cmd)


def apply_multiple_variations(cmd: str, variations: dict[str, str]) -> str:
    for p, v in variations.items():
        cmd = apply_variation(cmd, p, v)
    return cmd


def get_universal_variations() -> dict[str, dict[str, str]]:
    """Get all universal variations (for audit/debugging)."""
    load_variations()
    return dict(_UNIVERSAL_VARS)
