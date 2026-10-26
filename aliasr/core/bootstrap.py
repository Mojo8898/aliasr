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
    _seed_discovered_globals(app)


def _set_global(app, key: str, val: str) -> None:
    """Set a global in memory and persist it to globals.json, if it exists."""
    from aliasr.core.globals import save_global

    if key in app.globals:
        app.globals[key] = val
        save_global(key, val)


def _seed_discovered_globals(app):
    """Auto-populate globals for the current engagement, persisting to globals.json.

    Two sources, both written so the values become real persistent globals (the
    grid shows them this session, and they survive a restart):

    * Host globals (ip / fqdn / hostname / domain / dc_ip / dc_fqdn) from the
      current/stored host, incl. nxcdb pulls -- the same data the build form
      autofills. Only globals that already exist and are *blank* are filled, so
      a value the user set is never overwritten.
    * ``lhost`` from the local attacker interface (tun0, else eth0). Unlike the
      target host, this is a volatile local address (a VPN tap IP changes each
      session), so it is refreshed to the detected IP on every launch. When no
      tun0/eth0 is present (no IP found) any existing ``lhost`` is left as-is.
    """
    try:
        from aliasr.core.hosts import discovered_host_globals
        from aliasr.core.net import local_lhost

        discovered = discovered_host_globals()
        lhost = local_lhost()
    except Exception:
        return

    for key, val in discovered.items():
        if val and key in app.globals and not (app.globals.get(key) or "").strip():
            _set_global(app, key, val)

    if lhost:
        _set_global(app, "lhost", lhost)


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


def confirm_clear(creds: bool, hosts: bool, assume_yes: bool = False) -> bool:
    """Return True if a destructive ``aliasr clear`` should go ahead.

    Only the data-destroying targets (credentials / hosts) prompt — globals are
    cheap/local and clear without asking. ``assume_yes`` (``--yes``) skips the
    prompt for scripting, and a non-interactive stdin (EOF) aborts. The prompt
    warns when the clear will also reach NetExec.
    """
    if assume_yes or not (creds or hosts):
        return True

    # Nothing to delete -> don't bother asking (the clear reports "unchanged").
    if not _has_clearable_data(creds, hosts):
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


def _has_clearable_data(creds: bool, hosts: bool) -> bool:
    """Whether a destructive clear would actually remove credentials/hosts.

    Considers the aliasr store and, unless blocked, NetExec. Globals are not
    counted — they clear without a prompt regardless.
    """
    from aliasr.core.config import NXC_BLOCK_BULK_DELETE
    from aliasr.core.creds import has_stored_creds
    from aliasr.core.hosts import has_stored_hosts

    if creds and has_stored_creds():
        return True
    if hosts and has_stored_hosts():
        return True
    if not NXC_BLOCK_BULK_DELETE:
        try:
            from aliasr.core import nxc

            if creds and nxc.read_creds():
                return True
            if hosts and nxc.read_hosts():
                return True
        except Exception:
            pass
    return False


def clear_flags(globals: bool, creds: bool, hosts: bool = False) -> bool:
    """Clear selected stores, reporting whether each actually changed.

    Each clear returns True when it removed something; the printed line reflects
    that ("... cleared successfully!" vs "... unchanged").
    """
    tasks: list[tuple[str, callable]] = []

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
