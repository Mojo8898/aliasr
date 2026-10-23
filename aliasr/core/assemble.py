"""Assemble a stored cheat into an executable command.

Cheats store one command per line (a trailing ``\\`` continues the same command
onto the next line). At build time the lines are stitched back into a single
shell command, with a separator run before each step that announces the command
about to execute. The separator is a shell function ``s`` whose body comes from
``[build].separator`` in config.toml; it is invoked as ``s '<command>'`` so the
command text survives quoting. The whole thing is one ``\\``-continued line, so
it runs as a single logical command through every inject path.
"""

import re
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


def _label(cmd: str) -> str:
    """One-line form of a command, for the announce banner."""
    cmd = re.sub(r"\\\r?\n", " ", cmd)   # collapse continuations
    return re.sub(r"\s+", " ", cmd).strip()


def assemble(cmd: str, separator: str, wrap=None) -> str:
    """Stitch logical commands into one ``\\``-continued command with separators.

    ``wrap``, if given, is applied to each actual command (not the ``s``
    definition) -- used to prefix every command, e.g. with ``proxychains``.
    A single-command cheat gets no separator machinery, but is still wrapped.
    """
    w = wrap or (lambda c: c)
    cmds = split_commands(cmd)
    if len(cmds) <= 1:
        return w(cmd)
    parts = ["s(){ %s; }" % separator]
    for c in cmds:
        parts.append("s %s; %s" % (shlex.quote(_label(c)), w(c)))
    return " ; \\\n".join(parts)
