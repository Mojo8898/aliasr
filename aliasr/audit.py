import json
import os
import re
import tomllib
from collections import defaultdict
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from aliasr.core.cheats import (
    build_tag_index,
    clear_cache,
    get_loaded_cheats,
    load_cheats,
)
from aliasr.core.config import (
    BUILD_COLUMNS,
    CHEAT_PATHS,
    CHEATS_EXCLUDE,
    CHEATS_DEFAULT_GROUPING,
    CREDS_KDBX,
    CREDS_KEY,
    CREDS_MASK,
    DEFAULT_GLOBALS,
    GLOBALS_COLUMNS,
    GLOBALS_FILE,
    GLOBALS_HISTORY,
    GLOBALS_MAX_LEN,
    GLOBALS_AUTO_KRB,
    GLOBALS_ROWS,
    THEME,
)
from aliasr.core.globals import load_globals_raw
from aliasr.core.variations import load_variations
from aliasr.tui.theme import BUNDLED_THEMES


console = Console()


# ---------- Helpers ----------


def _panel(title: str, style: str = "white") -> Panel:
    """Create a styled panel."""
    return Panel.fit(f"[bold {style}]{title}[/]", border_style=style)


def _table(headers: list[str] = None, **kwargs) -> Table:
    """Create a consistent table."""
    t = Table(
        show_header=bool(headers),
        box=None,
        **kwargs
    )
    if headers:
        for h in headers:
            t.add_column(h)
    return t


def _rel(p: Path) -> Path:
    """Get relative path for display."""
    try:
        return p.relative_to(Path.cwd())
    except Exception:
        return p


def _get_md_files(show_excluded: bool = True) -> tuple[list[Path], list[Path]]:
    """Get markdown files from cheat paths."""
    md_files = []
    excluded = []
    
    for path in CHEAT_PATHS:
        if not path.exists():
            continue
        for md in path.rglob("*.md"):
            if md.name in CHEATS_EXCLUDE:
                excluded.append(md)
            else:
                md_files.append(md)
    
    if show_excluded and excluded:
        console.print("[bold]Excluded Files[/] [dim](from cheats_exclude config):[/]")
        for p in sorted(excluded):
            console.print(f"  [dim]⊘[/] {_rel(p)}")
        console.print()
    
    return md_files, excluded


def _diagnose_md(path: Path) -> str:
    """Quick diagnostic of markdown structure."""
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
        h2_count = len(re.findall(r"(?m)^\s*##\s+", txt))
        fence_count = len(re.findall(r"(?m)^\s*(```|~~~)", txt))
        return f"h2={h2_count} fences={fence_count}"
    except Exception as e:
        return f"error: {e}"


# ---------- Audit Functions ----------


def audit_cheats(list_all: bool = False) -> int:
    """Audit cheatsheets overview."""
    load_cheats()
    console.print(_panel("CHEATSHEET AUDIT OVERVIEW", "cyan"))
    console.print()
    
    md_files, excluded_files = _get_md_files(show_excluded=True)
    
    # Get all cheats
    all_cheats = get_loaded_cheats()
    tag_to_cheats, ordered_tags = build_tag_index()
    
    # Count cheats per file
    count_by_path = defaultdict(int)
    for c in all_cheats:
        count_by_path[Path(c.path)] += 1
    
    # Check for duplicate IDs
    by_id_paths = defaultdict(set)
    for c in all_cheats:
        by_id_paths[c.id].add(Path(c.path))
    
    dupes = {
        cid: sorted(paths)
        for cid, paths in by_id_paths.items()
        if len(paths) > 1
    }
    
    # Find files with zero cheats
    zeros = [
        (p, _diagnose_md(p))
        for p in md_files
        if count_by_path.get(p, 0) == 0
    ]
    
    # Summary table
    t = _table()
    t.add_column("Metric", style="dim")
    t.add_column("Value", style="bold")
    t.add_row("Roots scanned", f"[yellow]{[str(r) for r in CHEAT_PATHS]}[/]")
    t.add_row("Markdown files found", f"[blue]{len(md_files)}[/]")
    if excluded_files:
        t.add_row("Files excluded", f"[dim]{len(excluded_files)}[/]")
    t.add_row("Total cheats loaded", f"[green]{len(all_cheats)}[/]")
    t.add_row("Unique cheat IDs", f"[magenta]{len(by_id_paths)}[/]")
    console.print(t)
    
    # Report issues
    if dupes:
        console.print()
        console.print(_panel("DUPLICATE CHEAT IDs", "red"))
        for cid, paths in sorted(dupes.items()):
            console.print(f"\n  [yellow]{cid}:[/]")
            for p in paths:
                console.print(f"    [dim]•[/] {p}")
    
    if zeros:
        console.print()
        console.print(_panel("FILES WITH NO CHEATS [dim](possible parsing issues)[/]", "yellow"))
        for p, diag in zeros:
            console.print(f"\n  [red]{p}[/]")
            console.print(f"    [dim]Diagnostics: {diag}[/]")
    
    # Final summary
    console.print()
    console.print(_panel("SUMMARY"))
    console.print()
    
    s = _table()
    s.add_column("Status", style="dim")
    s.add_column("Count", style="bold")
    s.add_row("✓ Successfully parsed", f"[green]{len([1 for p in md_files if count_by_path.get(p, 0) > 0])} files[/]")
    s.add_row("⚠ Parse failures", f"[yellow]{len(zeros)} files[/]")
    s.add_row("⚠ Duplicate IDs", f"[yellow]{len(dupes)} groups[/]")
    console.print(s)
    
    # List all cheats if requested
    if list_all and ordered_tags:
        console.print()
        console.print(Panel.fit("CHEATS GROUPED BY CHEAT TAGS"))
        console.print()
        
        # Find untagged cheats
        untagged = [c for c in all_cheats if not c.cheat_tags]
        
        # Show untagged cheats first if any exist
        if untagged:
            tbl = Table(
                show_header=True,
                header_style="bold",
                expand=True,
                title=f"[dim]Untagged Cheats ({len(untagged)})[/]",
                box=box.ROUNDED,
            )
            tbl.add_column("ID", style="cyan", no_wrap=True)
            tbl.add_column("Title", style="yellow")
            tbl.add_column("Cmd Tags", style="magenta", no_wrap=True)
            tbl.add_column("Path", style="dim")
            
            for c in sorted(untagged, key=lambda x: (x.id, str(x.path))):
                cmd_tags_str = ", ".join(sorted(c.cmd_tags)) if c.cmd_tags else ""
                tbl.add_row(c.id, c.title, cmd_tags_str, str(c.path))
            
            console.print(tbl)
            console.print()
        
        # Show tagged cheats
        for tag in [t for t in ordered_tags if t != "all"]:
            group = tag_to_cheats.get(tag, [])
            if not group:
                continue
            
            tbl = Table(
                show_header=True,
                header_style="bold",
                expand=True,
                title=f"#{tag} ({len(group)})",
                box=box.ROUNDED,
            )
            tbl.add_column("ID", style="cyan", no_wrap=True)
            tbl.add_column("Title", style="yellow")
            tbl.add_column("Cmd Tags", style="magenta", no_wrap=True)
            tbl.add_column("Path", style="dim")
            
            for c in sorted(group, key=lambda x: (x.id, str(x.path))):
                cmd_tags_str = ", ".join(sorted(c.cmd_tags)) if c.cmd_tags else ""
                tbl.add_row(c.id, c.title, cmd_tags_str, str(c.path))
            
            console.print(tbl)
            console.print()
    else:
        console.print(f"\n[dim](Showing summary only. Use -l or --list-all to see all {len(all_cheats)} cheats)[/]\n")
    
    return 0


def audit_references() -> int:
    """Audit parameter references."""
    load_cheats()
    console.print(_panel("PARAMETER REFERENCE AUDIT", "cyan"))
    console.print()
    
    from aliasr.core.cheats import get_param_refs, _PH_RE
    
    md_files, _ = _get_md_files(show_excluded=True)
    all_cheats = get_loaded_cheats()
    
    # Stats
    total_cheats = 0
    total_params = 0
    total_refs = 0
    params_with = 0
    params_without = 0
    missing_refs = []
    existing_refs = []
    
    for p in sorted(md_files):
        cheats = [c for c in all_cheats if Path(c.path) == p]
        if not cheats:
            continue
        
        file_params = []
        file_missing = []
        
        for cheat in cheats:
            total_cheats += 1
            placeholders = _PH_RE.findall(cheat.cmd or "")
            params = list({tok.split("|", 1)[0] for tok in placeholders})
            
            for param in params:
                total_params += 1
                refs = get_param_refs(p, param)
                
                if refs:
                    params_with += 1
                    total_refs += len(refs)
                    file_params.append((cheat.title, param, len(refs)))
                else:
                    params_without += 1
                    file_missing.append((cheat.title, param))
        
        missing_refs.extend((p, t, prm) for t, prm in file_missing)
        
        if file_params:
            console.print(f"[bold yellow]{_rel(p)}[/]")
            console.print("  [green]✓ Parameters with references:[/]")
            for title, prm, count in file_params:
                console.print(f"    [dim]•[/] {title} :: [cyan]<{prm}>[/] ([green]{count} refs[/])")
                existing_refs.append((p, title, prm, count))
            console.print()
    
    # Summary
    console.print(_panel("SUMMARY"))
    stats = _table()
    stats.add_column("Metric", style="dim")
    stats.add_column("Value", style="bold")
    stats.add_row("Total cheats scanned", f"[blue]{total_cheats}[/]")
    stats.add_row("Total parameters found", f"[yellow]{total_params}[/]")
    stats.add_row("Parameters with references", f"[green]{params_with}[/]")
    stats.add_row("Parameters without references", f"[red]{params_without}[/]")
    stats.add_row("Total reference values", f"[magenta]{total_refs}[/]")
    console.print()
    console.print(stats)
    console.print()
    
    return 0


def audit_variations() -> int:
    """Audit variations configuration."""
    load_cheats()
    load_variations()
    
    console.print(_panel("VARIATIONS AUDIT", "cyan"))
    console.print()
    
    # Access the loaded variations from the module
    from aliasr.core.variations import _VARS as variations
    from aliasr.core.variations import get_universal_variations
    
    universal_vars = get_universal_variations()
    
    found_files = []
    for path in CHEAT_PATHS:
        vp = path / "variations.toml"
        if vp.is_file():
            found_files.append(vp)
    
    if not found_files:
        console.print("  [yellow]⚠ No variations.toml found in any cheats root[/]")
        console.print(f"    [dim]Searched: {', '.join(str(p) for p in CHEAT_PATHS)}[/]")
        return 0
    
    console.print("  [green]✓ Found variations:[/]")
    for f in found_files:
        console.print(f"    • {f}")
    
    if not variations and not universal_vars:
        console.print("\n  [yellow]⚠ variations are present but empty after merge[/]")
        return 0
    
    # Stats
    total_cmd_variations = sum(
        len(choices)
        for params in variations.values()
        for choices in params.values()
    )
    total_universal_variations = sum(
        len(choices)
        for choices in universal_vars.values()
    )
    
    console.print()
    stats = _table()
    stats.add_column("Metric", style="dim")
    stats.add_column("Value", style="bold")
    stats.add_row("Commands with variations", f"[cyan]{len(variations)}[/]")
    stats.add_row("Command-specific variations", f"[green]{total_cmd_variations}[/]")
    stats.add_row("Universal variations", f"[magenta]{total_universal_variations}[/]")
    stats.add_row("Total variations defined", f"[yellow]{total_cmd_variations + total_universal_variations}[/]")
    console.print(stats)
    
    # Show universal variations first
    if universal_vars:
        console.print()
        console.print(_panel("UNIVERSAL VARIATIONS"))
        for param in sorted(universal_vars):
            console.print(f"\n  [bold magenta]<{param}>:[/] [dim](applies to any command)[/]")
            for key, value in universal_vars[param].items():
                disp = value if len(value) <= 50 else value[:47] + "..."
                console.print(f"    [dim]•[/] [green]{key}:[/] {disp}")
    
    # List command-specific variations
    if variations:
        console.print()
        console.print(_panel("COMMAND-SPECIFIC VARIATIONS"))
        for cmd_prefix in sorted(variations):
            console.print(f"\n  [bold yellow]{cmd_prefix}:[/]")
            for param, vars_dict in variations[cmd_prefix].items():
                # Check if this overrides a universal variation
                override_indicator = ""
                if param in universal_vars:
                    override_indicator = " [dim red](overrides universal)[/]"
                console.print(f"    [cyan]<{param}>:[/]{override_indicator}")
                for key, value in vars_dict.items():
                    disp = value if len(value) <= 50 else value[:47] + "..."
                    console.print(f"      [dim]•[/] [green]{key}:[/] {disp}")
    
    # Map to cheats
    all_cheats = get_loaded_cheats()
    if all_cheats:
        console.print()
        console.print(_panel("CHEATS USING VARIATIONS"))
        
        matched_cmd_specific = defaultdict(list)
        matched_universal = defaultdict(list)
        
        for cheat in all_cheats:
            first = (cheat.cmd or "").split()[0] if cheat.cmd else ""
            
            # Extract parameters from command
            from aliasr.core.cheats import _PH_RE
            placeholders = _PH_RE.findall(cheat.cmd or "")
            param_names = {tok.split("|", 1)[0] for tok in placeholders}
            
            # Check command-specific variations
            params = variations.get(first)
            if params:
                for prm in param_names:
                    if prm in params:
                        matched_cmd_specific[first].append({
                            "title": cheat.title,
                            "param": prm,
                            "variations": list(params[prm].keys()),
                        })
            
            # Check universal variations (only for params not in command-specific)
            for prm in param_names:
                if prm in universal_vars:
                    # Skip if already has command-specific variation
                    if not (params and prm in params):
                        matched_universal[prm].append({
                            "title": cheat.title,
                            "command": first,
                        })
        
        # Display command-specific matches
        if matched_cmd_specific:
            console.print("\n  [bold yellow]Command-Specific:[/]")
            for prefix in sorted(matched_cmd_specific):
                console.print(f"\n    [yellow]{prefix}:[/]")
                for m in matched_cmd_specific[prefix]:
                    console.print(
                        f"      [dim]•[/] {m['title']} :: [cyan]<{m['param']}>[/] → [green][{', '.join(m['variations'])}][/]"
                    )
        
        # Display universal matches
        if matched_universal:
            console.print("\n  [bold magenta]Universal:[/]")
            for param in sorted(matched_universal):
                console.print(f"\n    [magenta]<{param}>:[/]")
                # Group by command for better readability
                by_cmd = defaultdict(list)
                for m in matched_universal[param]:
                    by_cmd[m['command']].append(m['title'])
                
                for cmd in sorted(by_cmd):
                    console.print(f"      [cyan]{cmd}:[/]")
                    for title in by_cmd[cmd]:
                        console.print(f"        [dim]•[/] {title}")
    
    # Potential issues
    console.print()
    console.print(_panel("POTENTIAL ISSUES"))
    issues = False
    
    # Check for unused command-specific variations
    if all_cheats:
        used_prefixes = {(c.cmd or "").split()[0] for c in all_cheats if c.cmd}
        unused_cmd = set(variations.keys()) - used_prefixes
        if unused_cmd:
            issues = True
            console.print("\n  [yellow]⚠ Command-specific variations for non-existent commands:[/]")
            for prefix in sorted(unused_cmd):
                console.print(f"    [red]• {prefix}[/]")
                for param in variations[prefix].keys():
                    console.print(f"      [dim]└─ {param}[/]")
    
    # Check for unused universal variations
    if all_cheats and universal_vars:
        all_params = set()
        for cheat in all_cheats:
            from aliasr.core.cheats import _PH_RE
            placeholders = _PH_RE.findall(cheat.cmd or "")
            all_params.update(tok.split("|", 1)[0] for tok in placeholders)
        
        unused_universal = set(universal_vars.keys()) - all_params
        if unused_universal:
            issues = True
            console.print("\n  [yellow]⚠ Universal variations for non-existent parameters:[/]")
            for param in sorted(unused_universal):
                console.print(f"    [red]• <{param}>[/]")
    
    # Check for empty variations
    for cmd_prefix, params in variations.items():
        for prm, vars_dict in params.items():
            empties = [k for k, v in vars_dict.items() if not str(v).strip()]
            if empties:
                issues = True
                console.print(f"\n  [yellow]⚠ Empty variation values in [{cmd_prefix}.{prm}]:[/]")
                for k in empties:
                    console.print(f"    [red]• {k}[/]")
    
    for prm, vars_dict in universal_vars.items():
        empties = [k for k, v in vars_dict.items() if not str(v).strip()]
        if empties:
            issues = True
            console.print(f"\n  [yellow]⚠ Empty universal variation values in [_.{prm}]:[/]")
            for k in empties:
                console.print(f"    [red]• {k}[/]")
    
    # Check for conflicts (same param has both universal and command-specific in same command)
    if matched_cmd_specific and universal_vars:
        console.print("\n  [dim]Checking for override patterns...[/]")
        override_count = 0
        for cmd_prefix, matches in matched_cmd_specific.items():
            for match in matches:
                if match['param'] in universal_vars:
                    override_count += 1
        if override_count:
            console.print(f"    [blue]ℹ {override_count} command-specific variations override universal ones[/]")
    
    if not issues:
        console.print("\n  [green]✓ No issues found[/]")
    
    console.print()
    return 0


def audit_config() -> int:
    """Audit configuration."""
    console.print(_panel("CONFIG AUDIT", "cyan"))
    console.print()
    
    # Check config file location
    config_path = None
    candidates = []
    
    if os.getenv("ALIASR_CONFIG"):
        candidates.append(Path(os.path.expanduser(os.environ["ALIASR_CONFIG"])))
    
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        # If XDG_CONFIG_HOME is explicitly set, use it
        candidates.append(Path(xdg) / "aliasr" / "config.toml")
    
    # Always check the default home location
    candidates.append(Path.home() / ".config" / "aliasr" / "config.toml")
    
    # Remove duplicates while preserving order
    seen = set()
    unique_candidates = []
    for path in candidates:
        path = path.resolve()  # Resolve to absolute path for comparison
        if path not in seen:
            seen.add(path)
            unique_candidates.append(path)
    
    console.print(_panel("CONFIG FILE SEARCH"))
    console.print()
    
    for path in candidates:
        exists = path.is_file()
        marker = "[green]✓[/]" if exists else "[red]✗[/]"
        console.print(f"  {marker} {path}")
        if exists and config_path is None:
            config_path = path
    
    if not config_path:
        console.print("\n  [yellow]⚠ No config.toml file found[/]")
        console.print("  [dim]Using built-in defaults[/]")
        return _audit_defaults()
    
    console.print(f"\n  [green]Using config:[/] {config_path}")
    
    # Parse user config
    try:
        with config_path.open("rb") as f:
            _ = tomllib.load(f)
        console.print("  [green]✓ Successfully parsed config.toml[/]")
    except Exception as e:
        console.print(f"  [red]✗ Failed to parse config.toml: {e}[/]")
        return 1
    
    console.print()
    issues = []
    warnings = []
    
    # Validate cheats configuration
    console.print(_panel("CHEATS CONFIGURATION"))
    console.print()
    
    for i, path in enumerate(CHEAT_PATHS):
        if path.exists() and path.is_dir():
            md_count = len(list(path.rglob("*.md")))
            console.print(f"  [green]✓[/] {path} ([cyan]{md_count} .md files[/])")
        elif path.exists():
            warnings.append(f"Cheat path exists but is not a directory: {path}")
            console.print(f"  [yellow]⚠[/] {path} [yellow](not a directory)[/]")
        else:
            console.print(f"  [red]✗[/] {path} [red](does not exist)[/]")
    
    # Validate globals configuration
    console.print()
    console.print(_panel("GLOBALS CONFIGURATION"))
    console.print()
    
    if GLOBALS_FILE.exists():
        if GLOBALS_FILE.is_file():
            try:
                gdata = load_globals_raw()
                console.print(f"  [green]✓ Globals file:[/] {GLOBALS_FILE}")
                console.print(f"    [dim]Contains {len(gdata)} globals[/]")
            except json.JSONDecodeError as e:
                issues.append(f"Globals file is not valid JSON: {e}")
                console.print(f"  [red]✗ Globals file invalid JSON: {e}[/]")
        else:
            warnings.append(f"Globals path exists but is not a file: {GLOBALS_FILE}")
            console.print(f"  [yellow]⚠ Globals file:[/] {GLOBALS_FILE} [yellow](not a file)[/]")
    else:
        console.print(f"  [dim]○ Globals file:[/] {GLOBALS_FILE} [dim](will be created)[/]")
    
    console.print(f"  History enabled: [{'green' if GLOBALS_HISTORY else 'red'}]{GLOBALS_HISTORY}[/]")
    if GLOBALS_HISTORY:
        console.print(f"  Max history length: [cyan]{GLOBALS_MAX_LEN}[/]")
    console.print(f"  Auto KRB5CCNAME: [{'green' if GLOBALS_AUTO_KRB else 'red'}]{GLOBALS_AUTO_KRB}[/]")
    
    # Validate credentials configuration
    console.print()
    console.print(_panel("CREDENTIALS CONFIGURATION"))
    console.print()
    
    console.print(f"  {'[green]✓[/]' if CREDS_KDBX.exists() else '[dim]○[/]'} KeePass DB: {CREDS_KDBX}")
    console.print(f"  {'[green]✓[/]' if CREDS_KEY.exists() else '[dim]○[/]'} Key file: {CREDS_KEY}")
    console.print(f"  Mask credentials: [{'green' if CREDS_MASK else 'red'}]{CREDS_MASK}[/]")
    
    # Validate theme
    console.print()
    console.print(_panel("THEME CONFIGURATION"))
    console.print()
    
    if THEME.name:
        all_themes = list(BUNDLED_THEMES.keys()) + [
            "textual-dark", "textual-light", "dracula", "monokai",
            "gruvbox", "tokyo-night", "nord", "solarized-dark", "solarized-light"
        ]
        if THEME.name in all_themes:
            src = "bundled theme" if THEME.name in BUNDLED_THEMES else "Textual built-in theme"
            console.print(f"  [green]✓ Using {src}:[/] [cyan]{THEME.name}[/]")
        else:
            warnings.append(f"Unknown theme name: {THEME.name}")
            console.print(f"  [yellow]⚠ Unknown theme:[/] {THEME.name} [yellow](may not exist)[/]")
    else:
        console.print("  [green]✓ Using custom color theme[/]")
        
        # Show custom colors
        ct = _table()
        ct.add_column("Key", style="dim")
        ct.add_column("Value")
        ct.add_column("Preview")
        
        for attr in ["primary", "secondary", "accent", "foreground", "background",
                     "success", "warning", "error", "surface", "panel"]:
            val = getattr(THEME, attr, None)
            if val and isinstance(val, str):
                if re.match(r"^#[0-9A-Fa-f]{6}$", val):
                    ct.add_row(f"theme_{attr}", val, f"[{val}]████[/]")
                else:
                    warnings.append(f"Invalid color format for theme_{attr}: {val}")
                    ct.add_row(f"theme_{attr}", f"[red]{val} (invalid)[/]", "")
        
        console.print(ct)
    
    # Validate layout
    console.print()
    console.print(_panel("LAYOUT CONFIGURATION"))
    console.print()
    
    lt = _table()
    lt.add_column("Setting", style="dim")
    lt.add_column("Value")
    
    for key, val in [
        ("globals_rows", GLOBALS_ROWS),
        ("globals_columns", GLOBALS_COLUMNS),
        ("build_columns", BUILD_COLUMNS),
    ]:
        if isinstance(val, int) and val > 0:
            lt.add_row(key, f"[green]{val}[/]")
        else:
            issues.append(f"{key} must be a positive integer: {val}")
            lt.add_row(key, f"[red]{val} (must be positive integer)[/]")
    
    console.print(lt)
    
    # Summary
    console.print()
    console.print(_panel("SUMMARY"))
    console.print()
    
    if not issues and not warnings:
        console.print("  [green]✓ Configuration is valid with no issues[/]")
    else:
        if issues:
            console.print(f"  [red]✗ {len(issues)} error(s) found:[/]")
            for i in issues:
                console.print(f"    [red]• {i}[/]")
        if warnings:
            console.print(f"  [yellow]⚠ {len(warnings)} warning(s) found:[/]")
            for w in warnings:
                console.print(f"    [yellow]• {w}[/]")
    
    console.print()
    return 1 if issues else 0


def _audit_defaults() -> int:
    """Audit default configuration when no custom config exists."""
    console.print()
    console.print(_panel("DEFAULT CONFIGURATION"))
    console.print("\n  [dim]No custom config file found, using built-in defaults:[/]\n")
    
    # Show all configuration sections
    sections = {
        "Cheats": {
            "Paths": str(CHEAT_PATHS),
            "Exclude": str(CHEATS_EXCLUDE),
            "Default Tag Type": str(CHEATS_DEFAULT_GROUPING),
        },
        "Globals": {
            "File": str(GLOBALS_FILE),
            "History": str(GLOBALS_HISTORY),
            "Max Length": str(GLOBALS_MAX_LEN),
            "Auto KRB5CCNAME": str(GLOBALS_AUTO_KRB),
            "Grid Rows": str(GLOBALS_ROWS),
            "Grid Columns": str(GLOBALS_COLUMNS),
        },
        "Default Globals": DEFAULT_GLOBALS,
        "Credentials": {
            "KeePass DB": str(CREDS_KDBX),
            "Key File": str(CREDS_KEY),
            "Mask": str(CREDS_MASK),
        },
        "Layout": {
            "Build Columns": str(BUILD_COLUMNS),
        },
        "Theme": {
            "Name": THEME.name or "custom",
        },
    }
    
    for section, values in sections.items():
        console.print(f"  [bold cyan][{section}][/]")
        t = _table()
        t.add_column("Key", style="dim")
        t.add_column("Value")
        
        if isinstance(values, dict):
            for k, v in values.items():
                t.add_row(k, str(v))
        else:
            t.add_row(section, str(values))
        
        console.print(t)
        console.print()
    
    return 0


# ---------- Main Entry Point ----------


def run_audit_cli(list_all: bool, which: str | None) -> int:
    """Run the appropriate audit command."""
    clear_cache()
    
    commands = {
        None: lambda: audit_cheats(list_all=list_all),
        "refs": audit_references,
        "vars": audit_variations,
        "conf": audit_config,
    }
    
    fn = commands.get(which)
    if not fn:
        console.print(f"[red]Unknown audit command: {which}[/]")
        return 1
    
    return fn()
