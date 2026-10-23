import os
from concurrent.futures import ThreadPoolExecutor


# ---------- Helpers ----------


def _load_cheats_data() -> None:
    """Load cheats - thread-safe."""
    from aliasr.core.cheats import load_cheats

    load_cheats()


def _load_globals_data() -> None:
    """Load globals - thread-safe."""
    from aliasr.core.globals import load_globals

    load_globals()


def _load_creds_data() -> None:
    """Prime the credential cache - thread-safe.

    The first load also pulls NetExec's credentials into the shared store, so
    doing it here overlaps that work with the cheats/globals load instead of
    stalling the first screen that reads credentials.
    """
    from aliasr.core.creds import load_creds

    load_creds()


def _create_app(execute: bool, pane: str | None, previous: bool) -> object:
    """Create fully configured app with tmux settings."""
    from aliasr.app import Aliasr

    in_tmux = bool(os.environ.get("TMUX"))
    tmux_current = None
    tmux_target = None

    if in_tmux:
        from aliasr.core.tmux import get_panes

        cur_pane, prev_pane = get_panes()
        tmux_current = cur_pane
        tmux_target = pane if pane is not None else (prev_pane if previous else None)

    return Aliasr(
        in_tmux=in_tmux,
        execute_cmd=execute,
        tmux_current_pane=tmux_current,
        tmux_target_pane=tmux_target,
    )


def _load_cached_data(app):
    from aliasr.core.cheats import get_loaded_cheats
    from aliasr.core.globals import load_globals

    app.cheats = get_loaded_cheats()
    app.globals = load_globals()


# ---------- Public API ----------


def launch_app(execute: bool, pane: str | None, previous: bool):
    """
    Optimal parallel startup - all heavy operations happen simultaneously.
    Returns fully configured app ready to run.
    """
    with ThreadPoolExecutor(max_workers=4) as executor:
        cheats_future = executor.submit(_load_cheats_data)
        globals_future = executor.submit(_load_globals_data)
        creds_future = executor.submit(_load_creds_data)
        app_future = executor.submit(_create_app, execute, pane, previous)

        app = app_future.result()
        cheats_future.result()
        globals_future.result()
        creds_future.result()

    _load_cached_data(app)
    return app


def confirm_clear(clear_cmd: str, assume_yes: bool = False) -> bool:
    """Return True if a destructive ``aliasr clear`` should go ahead.

    Only the data-destroying targets (creds / hosts / all) prompt — cache and
    globals are cheap/local and clear without asking. ``assume_yes`` (``--yes``)
    skips the prompt for scripting, and a non-interactive stdin (EOF) aborts.
    The prompt warns when the clear will also reach NetExec.
    """
    if assume_yes or clear_cmd not in ("creds", "hosts", "all"):
        return True

    # Nothing to delete -> don't bother asking (the clear reports "unchanged").
    if not _has_clearable_data(clear_cmd):
        return True

    from aliasr.core.config import NXC_BLOCK_BULK_DELETE

    msg = "Are you sure?"
    if not NXC_BLOCK_BULK_DELETE:
        msg += " This also clears matching entries in nxcdb."
    try:
        answer = input(f"{msg} [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def _has_clearable_data(clear_cmd: str) -> bool:
    """Whether a destructive clear would actually remove credentials/hosts.

    Considers the aliasr store and, unless blocked, NetExec. Cache/globals are
    not counted — they clear without a prompt regardless.
    """
    from aliasr.core.config import NXC_BLOCK_BULK_DELETE
    from aliasr.core.creds import has_stored_creds
    from aliasr.core.hosts import has_stored_hosts

    want_creds = clear_cmd in ("creds", "all")
    want_hosts = clear_cmd in ("hosts", "all")

    if want_creds and has_stored_creds():
        return True
    if want_hosts and has_stored_hosts():
        return True
    if not NXC_BLOCK_BULK_DELETE:
        try:
            from aliasr.core import nxc

            if want_creds and nxc.read_creds():
                return True
            if want_hosts and nxc.read_hosts():
                return True
        except Exception:
            pass
    return False


def clear_flags(cache: bool, globals: bool, creds: bool, hosts: bool = False) -> bool:
    """Clear selected stores, reporting whether each actually changed.

    Each clear returns True when it removed something; the printed line reflects
    that ("... cleared successfully!" vs "... unchanged").
    """
    tasks: list[tuple[str, callable]] = []

    if cache:
        from aliasr.core.cheats import clear_cache

        tasks.append(("Cache", clear_cache))

    if globals:
        from aliasr.core.globals import clear_globals

        tasks.append(("Globals", clear_globals))

    if creds:
        from aliasr.core.creds import clear_creds

        tasks.append(("Credentials", clear_creds))

    if hosts:
        from aliasr.core.hosts import clear_hosts

        tasks.append(("Hosts", clear_hosts))

    if not tasks:
        return False

    results: dict[str, bool | None] = {}
    if len(tasks) == 1:
        name, fn = tasks[0]
        try:
            results[name] = bool(fn())
        except Exception as e:
            print(f"Warning: {e}")
            results[name] = None
    else:
        with ThreadPoolExecutor(max_workers=2) as ex:
            futs = {name: ex.submit(fn) for name, fn in tasks}
        for name, fut in futs.items():
            try:
                results[name] = bool(fut.result())
            except Exception as e:
                print(f"Warning: {e}")
                results[name] = None

    for name, _ in tasks:
        changed = results.get(name)
        if changed is None:
            continue  # a warning was already printed
        print(f"{name} cleared successfully!" if changed else f"{name} unchanged")
    return True
