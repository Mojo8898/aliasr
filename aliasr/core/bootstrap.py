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

    from aliasr.core.config import NXC_BLOCK_BULK_DELETE

    msg = "Are you sure?"
    if not NXC_BLOCK_BULK_DELETE:
        msg += " This also clears matching entries in nxcdb."
    try:
        answer = input(f"{msg} [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


def clear_flags(cache: bool, globals: bool, creds: bool, hosts: bool = False) -> bool:
    """Clear selected stores."""
    tasks: list[tuple[str, callable]] = []

    if cache:
        from aliasr.core.cheats import clear_cache

        tasks.append(("Cache cleared successfully!", clear_cache))

    if globals:
        from aliasr.core.globals import clear_globals

        tasks.append(("Globals cleared successfully!", clear_globals))

    if creds:
        from aliasr.core.creds import clear_creds

        tasks.append(("Credentials cleared successfully!", clear_creds))

    if hosts:
        from aliasr.core.hosts import clear_hosts

        tasks.append(("Hosts cleared successfully!", clear_hosts))

    if not tasks:
        return False

    if len(tasks) == 1:
        msg, fn = tasks[0]
        try:
            fn()
            print(msg)
        except Exception as e:
            print(f"Warning: {e}")
        return True

    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(fn) for _, fn in tasks]
        for f in futs:
            try:
                f.result()
            except Exception as e:
                print(f"Warning: {e}")
    for msg, _ in tasks:
        print(msg)
    return True
