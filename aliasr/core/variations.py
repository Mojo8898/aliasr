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
                for param, choices in (
                    params if isinstance(params, dict) else {}
                ).items()
            }
        else:
            # Regular command-specific variations
            result[str(cmd)] = {
                str(param): (choices if isinstance(choices, dict) else {})
                for param, choices in (
                    params if isinstance(params, dict) else {}
                ).items()
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


def _param_table(head: str, param: str) -> dict[str, str] | None:
    """The {key: value} choices for ``param`` on a command with the given head.

    Command-specific wins over universal; None if neither defines it.
    """
    return _VARS.get(head, {}).get(param) or _UNIVERSAL_VARS.get(param)


def get_all_variations(cmd: str, params: list[str]) -> dict[str, list[Variation]]:
    """Collapsed, per-line variations for a (possibly multi-line) command.

    Each line is resolved against its *own* command head, so a placeholder on
    line 4 uses line 4's command's variation set -- not line 1's. A placeholder
    that appears on several lines is collapsed into a single entry (one tab)
    whose option keys are those shared by *every* occurrence. The user picks a
    key once and ``apply_selection`` expands it per line, so one choice renders
    with each command's own syntax (e.g. Kerberos -> ``-k`` for bloodyAD,
    ``--use-kcache`` for nxc).

    The returned ``Variation.value`` is the option *key* (not the substituted
    string); expansion to the per-line value happens in ``apply_selection`` /
    the live preview via ``lookup_value``. Param and key order follow first
    appearance.
    """
    load_variations()

    wanted = set(params)
    order: list[str] = []
    # param -> list of key-lists, one per resolvable occurrence
    occ: dict[str, list[list[str]]] = {}
    # param -> True if every occurrence resolves to the same single head
    heads: dict[str, set[str]] = {}

    for line in cmd.split("\n"):
        head = _head(line)
        seen_in_line: set[str] = set()
        for tok in re.findall(r"<([^>\s]+)>", line):
            p = tok.split("|", 1)[0]
            if p not in wanted or p in seen_in_line:
                continue
            seen_in_line.add(p)
            table = _param_table(head, p)
            if not table:
                continue
            if p not in occ:
                occ[p] = []
                heads[p] = set()
                order.append(p)
            occ[p].append(list(table.keys()))
            heads[p].add(head)

    result: dict[str, list[Variation]] = {}
    for p in order:
        key_lists = occ[p]
        # Collapse: keep keys present in every occurrence, first-seen order.
        shared = [k for k in key_lists[0] if all(k in ks for ks in key_lists)]
        if not shared:
            continue
        single_head = next(iter(heads[p])) if len(heads[p]) == 1 else "_"
        is_univ = single_head == "_" or single_head not in _VARS
        result[p] = [
            Variation(k, k, p, single_head, is_universal=is_univ) for k in shared
        ]

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


def command_head(line: str) -> str:
    """Public: the command head (first token) of a single command line."""
    return _head(line)


def lookup_value(head: str, param: str, key: str) -> str | None:
    """The substitution string for ``key`` of ``param`` on a command with the
    given head, or None if that command has no such variation/key."""
    load_variations()
    table = _param_table(head, param)
    if table and key in table:
        return table[key]
    return None


def apply_selection(cmd: str, selected: dict[str, str]) -> str:
    """Expand chosen variation *keys* into a (possibly multi-line) command.

    Each line is resolved against its own head, so a single pick (e.g.
    ``auth`` -> ``Kerberos``) renders with each command's own syntax. A line
    whose command has no entry for the chosen key is left untouched (its
    placeholder survives to the build screen).
    """
    load_variations()
    out = []
    for line in cmd.split("\n"):
        head = _head(line)
        for param, key in selected.items():
            value = lookup_value(head, param, key)
            if value is not None:
                line = apply_variation(line, param, value)
        out.append(line)
    return "\n".join(out)


def get_universal_variations() -> dict[str, dict[str, str]]:
    """Get all universal variations (for audit/debugging)."""
    load_variations()
    return dict(_UNIVERSAL_VARS)
