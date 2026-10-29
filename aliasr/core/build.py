"""Non-interactive command construction, shared by the TUI build screen and
external callers (e.g. recon-setup).

Turns a cheat body plus chosen values/selections into the final executable
command, in one place so every caller produces identical output:

1. expand variation selections (``apply_selection``),
2. fill ``<placeholder>`` values,
3. stitch into the ``arun`` / ``AR_SKEW`` chain (``assemble``), and
4. apply any encode tag (``ps_encode`` / ``sh_encode``).

The TUI applies variations in its own screen, so it calls :func:`render` with
``selections=None`` (its ``cmd`` is already expanded); a headless caller passes
its chosen ``selections`` and lets ``render`` expand them.
"""

import base64
import re

from aliasr.core.assemble import assemble
from aliasr.core.variations import apply_selection

PLACEHOLDER_RE = re.compile(r"<([^>\s]+)>")


class BuildError(Exception):
    """A placeholder could not be resolved while building in strict mode."""


def fill_placeholders(cmd: str, values: dict[str, str], *, strict: bool = False) -> str:
    """Replace ``<name>`` / ``<name|default>`` tokens from *values*.

    A name present in *values* wins (even if empty — an explicit clear); else a
    token default is used; else, in ``strict`` mode, :class:`BuildError` is
    raised (headless callers want a typo to fail loudly), otherwise the token is
    dropped to empty (the TUI's lenient behavior — it seeds values up front).
    """

    def repl(m: re.Match[str]) -> str:
        token = m.group(1)
        name, _, default = token.partition("|")
        if name in values and values[name] is not None:
            return str(values[name])
        if default:
            return default
        if strict:
            raise BuildError(f"unbound placeholder <{token}>")
        return ""

    return PLACEHOLDER_RE.sub(repl, cmd)


def apply_encode_tags(cmd: str, tags) -> str:
    """Wrap *cmd* per an encode build tag, or return it unchanged."""
    if "ps_encode" in tags:
        return (
            f"powershell -e {base64.b64encode(cmd.encode('utf-16le')).decode('ascii')}"
        )
    if "sh_encode" in tags:
        return f"echo {base64.b64encode(cmd.encode('utf-8')).decode('ascii')} | base64 -d | /bin/sh"
    return cmd


def skew_target(
    build_tags, values: dict[str, str], *, fallback: str = ""
) -> str | None:
    """The DC-clock-skew target for a ``#faketime`` cheat, else ``None``.

    Prefers an ``ip``/``dc_ip`` the caller resolved, then *fallback* (e.g. a
    stored global), so a cheat with no ``<ip>``/``<dc_ip>`` placeholder (a lone
    ``getTGT``) still runs skewed rather than silently unskewed.
    """
    if "faketime" not in build_tags:
        return None
    return values.get("ip") or values.get("dc_ip") or fallback or None


def _prefix_wrapper(prefix: str):
    """A per-command wrapper applying *prefix* (``{cmd}`` placeholder or prepend)."""
    if not prefix:
        return lambda c: c

    def wrap(c: str) -> str:
        return prefix.replace("{cmd}", c) if "{cmd}" in prefix else f"{prefix}{c}"

    return wrap


def render(
    cmd: str,
    values: dict[str, str],
    *,
    selections: dict[str, str] | None = None,
    build_tags=frozenset(),
    cheat_tags=(),
    skew_fallback: str = "",
    prefix: str = "",
    strict: bool = False,
) -> str:
    """Build the final executable command from a cheat body.

    *selections* (chosen variation keys) are expanded first when given; *values*
    fill the remaining placeholders.  ``build_tags`` drives skew/encode, and
    ``cheat_tags`` marks a ``#target/local`` cheat (emitted bare).  A ``ps_encode``
    cheat skips the ``arun`` chain (it's bash-only); every other cheat is
    assembled, then any ``sh_encode`` tag wraps the whole chain.
    """
    tags = frozenset(build_tags)
    if selections:
        cmd = apply_selection(cmd, selections)
    cmd = fill_placeholders(cmd, values, strict=strict)
    wrap = _prefix_wrapper(prefix)

    if "ps_encode" in tags:
        return wrap(apply_encode_tags(cmd, tags))

    local = "target/local" in cheat_tags
    skew = skew_target(tags, values, fallback=skew_fallback)
    return apply_encode_tags(
        assemble(cmd, skew_target=skew, local=local, wrap=wrap), tags
    )
