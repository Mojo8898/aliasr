# ---------- Internal ----------


def _tmux(*args: str) -> str | None:
    """Run a tmux command; return stdout or None on failure."""
    try:
        from subprocess import run

        p = run(["tmux", *args], capture_output=True, text=True, timeout=1.0)
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
