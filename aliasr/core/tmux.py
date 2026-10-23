# ---------- Internal ----------


def _deskewed_env() -> dict[str, str] | None:
    """Env for the tmux subprocess with any libfaketime clock skew removed.

    Under faketime/skewrun (the DC-clock-skew workflow), the shell preloads
    libfaketime and the whole session runs on a skewed clock. A tmux *client*
    launched from there inherits that preload and skew, and then hangs talking
    to the real-clock tmux *server* -- it only unblocks when our 1s timeout
    fires, adding ~1s to every tmux call (startup detection, pane targeting).

    tmux has no need for faketime, so we drop libfaketime from ``LD_PRELOAD``
    and unset the ``FAKETIME*`` vars for the child only, leaving the rest of the
    environment intact. Returns ``None`` when no skew is present, so the normal
    (overwhelmingly common) path runs tmux with the inherited environment.
    """
    import os

    preload = os.environ.get("LD_PRELOAD", "")
    faketime_vars = [k for k in os.environ if k == "FAKETIME" or k.startswith("FAKETIME_")]
    if "faketime" not in preload.lower() and not faketime_vars:
        return None

    env = dict(os.environ)
    # LD_PRELOAD entries are whitespace- or colon-separated; keep the non-faketime ones.
    kept = [p for p in preload.replace(":", " ").split() if "faketime" not in p.lower()]
    if kept:
        env["LD_PRELOAD"] = os.pathsep.join(kept)
    else:
        env.pop("LD_PRELOAD", None)
    for k in faketime_vars:
        env.pop(k, None)
    return env


def _tmux(*args: str) -> str | None:
    """Run a tmux command; return stdout or None on failure."""
    try:
        from subprocess import run

        p = run(
            ["tmux", *args],
            capture_output=True,
            text=True,
            timeout=1.0,
            env=_deskewed_env(),
        )
        return p.stdout.strip() if p.returncode == 0 else None
    except Exception:
        return None


# ---------- Public API ----------


def get_current_pane() -> str | None:
    """Current pane index as a string (or None)."""
    return _tmux("display-message", "-p", "#{pane_index}")


def get_panes() -> tuple[str | None, str | None]:
    """Return (current_pane, previous_pane) indices as strings."""
    s = _tmux("display-message", "-p", "#{pane_index}:#{window_panes}")
    if not s or ":" not in s:
        return None, None
    try:
        cur, total = (int(x) for x in s.split(":", 1))
    except ValueError:
        return None, None

    if total <= 1:
        return str(cur), str(cur)

    prev = cur - 1 if cur > 0 else total - 1
    return str(cur), str(prev)


def set_env(var: str, value: str) -> None:
    """Set a tmux environment variable for the current session."""
    _tmux("set-environment", var, value)


def send_cmd(cmd: str, pane: str) -> None:
    """Send a command to a target tmux pane"""
    _tmux("send-keys", "-t", pane, cmd, "C-m")


def send_and_select(cmd: str, pane: str) -> None:
    """Send a command to a tmux pane and select it afterwards."""
    _tmux("send-keys", "-t", pane, cmd, ";", "select-pane", "-t", pane)
