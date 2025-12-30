import os
import re
import pickle
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from aliasr.core.config import CHEAT_PATHS, CHEATS_EXCLUDE


@dataclass(frozen=True, slots=True)
class Cheat:
    """Represents a single cheat/command from markdown files."""
    id: str
    title: str
    cmd: str
    path: str
    cheat_tags: tuple[str, ...] = ()
    cmd_tags: tuple[str, ...] = ()


_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$")
_H2_RE = re.compile(r"^\s*##\s+(.+?)\s*$")
_FENCE_OPEN_RE = re.compile(r"^\s*(```|~~~)")
_ID_SANITIZE_RE = re.compile(r"\W+")
_TAG_RE = re.compile(r"#([\w/-]+)")
_PH_RE = re.compile(r"<([^>\s]+)>")
_PARAM_HEADER_RE = re.compile(r"^\s*-\s*([A-Za-z0-9_:-]+)\s*$")

_ALL: list[Cheat] = []
_TAGS: list[str] = []
_TAG_TO: dict[str, list[Cheat]] = {}
_REFS_BY_FILE: dict[str, dict[str, list[str]]] = {}
_DEFAULTS_BY_FILE: dict[str, dict[str, str]] = {}


# ---------- Parsing ----------


def _scan_md_files() -> list[Path]:
    """Scan all markdown files in cheat paths."""
    out: list[Path] = []
    for base in CHEAT_PATHS:
        if not base.exists() or not base.is_dir():
            continue
        for root, _dirs, files in os.walk(base):
            for fn in files:
                if not fn.endswith(".md") or fn in CHEATS_EXCLUDE:
                    continue
                out.append(Path(root) / fn)
    return out


def _parse_markdown(
    path: Path, content: str
) -> tuple[list[Cheat], dict[str, list[str]], dict[str, str]]:
    """Parse a markdown file for cheats, references, and defaults."""
    cheats: list[Cheat] = []
    refs: dict[str, list[str]] = defaultdict(list)
    defaults: dict[str, str] = {}

    # State tracking
    cheat_tags: set[str] = set()
    cmd_title = None
    cmd_tags: set[str] = set()
    in_fence = False
    fence = ""
    buf: list[str] = []
    current_ref = None

    for raw in content.splitlines():
        line = raw.rstrip()

        if not in_fence:
            # Check for H1 header (resets cheat context)
            if _H1_RE.match(line):
                cheat_tags.clear()
                cmd_title = None
                cmd_tags.clear()
                continue

            # Check for H2 header (command title)
            if m := _H2_RE.match(line):
                cmd_title = m.group(1).strip()
                cmd_tags.clear()
                continue

            # Process tags
            s = line.strip()
            if s.startswith("#") and not s.startswith("##"):
                for tag in _TAG_RE.findall(s):
                    (cmd_tags if cmd_title else cheat_tags).add(tag.lower())
                continue

            # Start of code fence
            if cmd_title and (fm := _FENCE_OPEN_RE.match(line)):
                in_fence = True
                fence = fm.group(1)
                buf.clear()
                continue

            # Empty line resets reference context
            if not s:
                current_ref = None
                continue

            # Parameter reference header
            if m := _PARAM_HEADER_RE.match(s):
                current_ref = m.group(1).strip()
                refs.setdefault(current_ref, [])
                continue

            # Reference value
            if current_ref:
                refs[current_ref].append(s)
        else:
            # End of code fence
            if line.strip().startswith(fence):
                cmd = "\n".join(buf).strip()
                if cmd and cmd_title:
                    cid = _ID_SANITIZE_RE.sub("_", cmd_title.lower()).strip("_")
                    cheats.append(
                        Cheat(
                            id=cid,
                            title=cmd_title,
                            cmd=cmd,
                            path=str(path),
                            cheat_tags=tuple(sorted(cheat_tags)),
                            cmd_tags=tuple(sorted(cmd_tags)),
                        )
                    )
                cmd_title = None
                cmd_tags.clear()
                in_fence = False
                fence = ""
                buf.clear()
            else:
                buf.append(line.rstrip("\n"))

    # Extract defaults from placeholders in commands
    for ch in cheats:
        for tok in _PH_RE.findall(ch.cmd):
            name, *rest = tok.split("|", 1)
            if rest and name not in defaults:
                v = rest[0].strip()
                if v:
                    defaults[name] = v

    return cheats, refs, defaults


# ---------- Caching ----------


def _build_from_files(files: list[Path]) -> None:
    """Build cheats index from markdown files."""
    global _ALL, _TAGS, _TAG_TO, _REFS_BY_FILE, _DEFAULTS_BY_FILE

    all_cheats: list[Cheat] = []
    refs_by_file: dict[str, dict[str, list[str]]] = {}
    defaults_by_file: dict[str, dict[str, str]] = {}

    # Parse all files
    for p in files:
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        cheats, refs, defaults = _parse_markdown(p, content)
        all_cheats.extend(cheats)
        refs_by_file[str(p)] = refs
        defaults_by_file[str(p)] = defaults

    # Build tag index
    tag_to: dict[str, list[Cheat]] = defaultdict(list)
    for ch in all_cheats:
        for t in ch.cheat_tags:
            tag_to[t].append(ch)

    tags = ["all"] + sorted(tag_to.keys())
    tag_to["all"] = all_cheats

    # Update global state
    _ALL = all_cheats
    _TAGS = tags
    _TAG_TO = tag_to
    _REFS_BY_FILE = refs_by_file
    _DEFAULTS_BY_FILE = defaults_by_file


def _cache_path() -> Path:
    """Get path to cheats pickle cache."""
    root = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")) / "aliasr"
    root.mkdir(parents=True, exist_ok=True)
    return root / "cheats_cache.pkl"


def _save_cache(cache_path: Path) -> None:
    """Save cache with direct object pickling and index-based tags."""
    # Build index mapping for tag storage
    cheat_to_idx = {id(ch): i for i, ch in enumerate(_ALL)}

    # Convert tag_to to use indices instead of objects (skip "all")
    tag_to_indices = {}
    for tag, cheats in _TAG_TO.items():
        if tag != "all":
            tag_to_indices[tag] = [cheat_to_idx[id(ch)] for ch in cheats]

    payload = {
        "all": _ALL,  # Pickle Cheat objects directly - NO asdict()
        "tags": _TAGS,
        "tag_to_indices": tag_to_indices,  # Store indices, not objects
        "refs_by_file": _REFS_BY_FILE,
        "defaults_by_file": _DEFAULTS_BY_FILE,
    }

    # Atomic write
    tmp = cache_path.with_suffix(".tmp")
    with tmp.open("wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    tmp.replace(cache_path)


# ---------- Public API ----------


def load_cheats() -> None:
    """Just load cache, don't verify."""
    global _ALL, _TAGS, _TAG_TO, _REFS_BY_FILE, _DEFAULTS_BY_FILE

    cp = _cache_path()
    if cp.exists():
        with cp.open("rb") as f:
            blob = pickle.load(f)

        # Direct assignment - no conversion needed
        _ALL = blob["all"]
        _TAGS = blob["tags"]
        _REFS_BY_FILE = blob["refs_by_file"]
        _DEFAULTS_BY_FILE = blob["defaults_by_file"]

        # Rebuild _TAG_TO from indices
        tag_to_indices = blob.get("tag_to_indices", {})
        _TAG_TO = {}
        for tag, indices in tag_to_indices.items():
            _TAG_TO[tag] = [_ALL[i] for i in indices]
        _TAG_TO["all"] = _ALL
        return

    # Only build if no cache exists
    files = _scan_md_files()
    _build_from_files(files)
    _save_cache(cp)


def clear_cache() -> None:
    """Clear the cheats cache, forcing rebuild on next load."""
    cp = _cache_path()
    if cp.exists():
        cp.unlink()


def build_tag_index() -> tuple[dict[str, list[Cheat]], list[str]]:
    """Get tag-to-cheats mapping and ordered tag list."""
    return _TAG_TO, _TAGS


def get_loaded_cheats() -> list[Cheat]:
    """Get all loaded cheats."""
    return _ALL


def get_param_refs(md_path: Path, param: str) -> list[str]:
    """Get reference values for a parameter in a specific markdown file."""
    return _REFS_BY_FILE.get(str(md_path), {}).get(param, [])


def get_param_default(md_path: Path, param: str) -> str | None:
    """Get default value for a parameter in a specific markdown file."""
    return _DEFAULTS_BY_FILE.get(str(md_path), {}).get(param)
