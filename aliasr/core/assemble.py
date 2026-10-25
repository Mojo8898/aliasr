"""Assemble a stored cheat into an executable command.

Cheats store one command per line (a trailing ``\\`` continues the same command
onto the next line). At build time the lines are stitched back into a single
``\\``-continued shell command.

A multi-line cheat is stitched into an ``arun`` chain: each logical command is
prefixed with ``arun`` -- a small standalone wrapper the user installs on PATH
(see ``scripts/arun``) that announces the command (the ``=== <cmd> ===``
banner) and, when ``$AR_SKEW`` is set, runs it under ``skewrun`` to correct DC
clock skew. The command is emitted **unquoted**, so a trailing ``&& export ...``
is parsed by the *parent* shell and its side effects persist across steps (a
standalone ``arun`` runs each step in a child and cannot mutate the parent env).

Commands that skip the ``arun`` chain and emit bare, ``\\``-continued:

* a single-command cheat with no skew (nothing to announce or chain), and
* a ``#target/local`` cheat -- it's injected into a foreign ssh/winrm shell on
  the target, which won't have ``arun``/``skewrun`` installed (so it emits bare
  even under ``#faketime``; skew can't be corrected on the remote host).

A single-command ``#faketime`` cheat (e.g. a lone ``getTGT.py``) still needs skew,
so it runs under one ``arun`` with ``AR_SKEW`` scoped to that call
(``AR_SKEW=<target> arun <cmd>``) rather than emitting bare.
"""

import shlex


def split_commands(cmd: str) -> list[str]:
    """Split a stored cheat into its logical commands.

    A bare newline ends a command; a line that ends in ``\\`` or a trailing shell
    operator (``|``, ``&&``, ``||``) continues the current command onto the next
    line, so a piped pipeline or a ``\\``-wrapped ``for``/``awk``/function body
    stays a single step. (A multi-line compound block must therefore use ``\\`` on
    each line; the shipped cheats keep such blocks on one line.)
    """
    out: list[str] = []
    cur: list[str] = []
    for line in cmd.split("\n"):
        cur.append(line)
        stripped = line.rstrip()
        if stripped.endswith(("\\", "|", "&&", "||")):
            continue
        out.append("\n".join(cur))
        cur = []
    if cur:
        out.append("\n".join(cur))
    return [c for c in out if c.strip()]


def assemble(
    cmd: str,
    *,
    skew_target: str | None = None,
    local: bool = False,
    wrap=None,
) -> str:
    """Stitch logical commands into one ``\\``-continued executable command.

    ``skew_target``, when set, makes the chain run under skewrun: a leading
    ``export AR_SKEW=<target>`` is emitted and ``arun`` reads it. ``local`` marks
    a ``#target/local`` cheat, which is emitted bare (no ``arun``) because it runs
    on a foreign host. ``wrap``, if given, is applied to each actual command
    (e.g. to prefix ``proxychains``); it wraps the command inside ``arun``.
    """
    w = wrap or (lambda c: c)
    cmds = split_commands(cmd)

    # A `#target/local` cheat is injected into a foreign ssh/winrm shell with no
    # arun/skewrun installed, so it always emits bare -- even when #faketime is set
    # (skew can't be corrected on the remote host anyway).
    if local:
        if len(cmds) <= 1:
            return w(cmd)
        return " ; \\\n".join(w(c) for c in cmds)

    # A single command gets no chain. With no skew it emits bare (nothing to
    # announce). A single #faketime command still needs skew, so it runs under
    # arun with AR_SKEW scoped to that one call (the prefix assignment never leaks
    # into the parent env, and arun still skips skewrun when FAKETIME is set).
    if len(cmds) <= 1:
        if skew_target:
            return "AR_SKEW=%s arun %s" % (shlex.quote(skew_target), w(cmd))
        return w(cmd)

    parts: list[str] = []
    if skew_target:
        parts.append("export AR_SKEW=%s" % shlex.quote(skew_target))
    # Unquoted on purpose: a step's trailing `&& export ...` must be seen by the
    # parent shell so its env change survives into later steps.
    parts.extend("arun %s" % w(c) for c in cmds)
    return " ; \\\n".join(parts)
