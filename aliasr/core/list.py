from rich.console import Console
from rich.table import Table
from rich import box


def list_globals() -> int:
    """List all globals and their current values."""
    from aliasr.core.globals import load_globals, load_globals_raw
    from aliasr.core.config import GLOBALS_HISTORY

    console = Console()

    # Load globals (preserves file order)
    current_globals = load_globals()
    raw_globals = load_globals_raw() if GLOBALS_HISTORY else {}

    if not current_globals:
        console.print("[yellow]No globals found.[/]")
        return 0

    # Create table
    table = Table(
        title="[bold cyan]Global Variables[/]",
        box=box.ROUNDED,
        show_header=True,
    )

    table.add_column("Global", style="cyan", no_wrap=True)
    table.add_column("Current Value", style="yellow")
    if GLOBALS_HISTORY:
        table.add_column("History Count", style="dim", justify="center")

    # Display globals in the order they appear in the file (preserved by load_globals)
    for key in current_globals.keys():
        value = current_globals[key]
        display_value = str(value) if value else "[dim]<empty>[/]"

        if GLOBALS_HISTORY and key in raw_globals:
            history_count = len(raw_globals[key])
            table.add_row(key, display_value, str(history_count))
        else:
            table.add_row(key, display_value)

    console.print()
    console.print(table)
    console.print()
    console.print(f"[green]Total:[/] {len(current_globals)} globals")
    if GLOBALS_HISTORY:
        total_history = sum(len(v) for v in raw_globals.values())
        console.print(f"[dim]History entries:[/] {total_history}")

    return 0


def list_creds() -> int:
    """List all saved credentials."""
    from aliasr.core.creds import load_creds
    from aliasr.core.config import CREDS_MASK

    console = Console()

    try:
        creds = load_creds()
    except Exception as e:
        console.print(f"[red]Error loading credentials:[/] {e}")
        return 1

    if not creds:
        console.print("[yellow]No credentials found.[/]")
        return 0

    # Create table
    table = Table(
        title="[bold cyan]Saved Credentials[/]",
        box=box.ROUNDED,
        show_header=True,
    )

    table.add_column("#", style="dim", justify="center")
    table.add_column("Username", style="cyan", no_wrap=True)
    table.add_column("Password", style="yellow")
    table.add_column("NT Hash", style="green")
    table.add_column("Domain", style="blue")

    # Display credentials
    for i, cred in enumerate(creds, 1):
        # Mask sensitive data if configured
        if CREDS_MASK:
            password_display = (
                "•" * min(len(cred.password), 16)
                if cred.password
                else "[dim]<empty>[/]"
            )
            hash_display = (
                "•" * min(len(cred.hash), 16) if cred.hash else "[dim]<empty>[/]"
            )
        else:
            password_display = cred.password if cred.password else "[dim]<empty>[/]"
            hash_display = cred.hash if cred.hash else "[dim]<empty>[/]"

        username_display = cred.username if cred.username else "[dim]<empty>[/]"
        domain_display = cred.domain if cred.domain else "[dim]<empty>[/]"

        table.add_row(
            str(i), username_display, password_display, hash_display, domain_display
        )

    console.print()
    console.print(table)
    console.print()
    console.print(
        f"[green]Total:[/] {len(creds)} credential{'s' if len(creds) != 1 else ''}"
    )
    if CREDS_MASK:
        console.print(
            "[dim]Note: Credentials are masked. Set 'creds.mask = false' in config to show values.[/]"
        )

    return 0


def list_all() -> int:
    """List both globals and credentials."""
    # List globals first
    list_globals()

    print()  # Add spacing between tables

    # Then list credentials
    list_creds()

    return 0


def run_list(what: str) -> int:
    """Execute list command based on subcommand."""
    if what == "globals":
        return list_globals()
    elif what == "creds":
        return list_creds()
    elif what == "all":
        return list_all()
    else:
        from rich.console import Console

        console = Console()
        console.print(f"[red]Unknown list command:[/] {what}")
        console.print("[dim]Use 'aliasr list globals' or 'aliasr list creds'[/]")
        return 1
