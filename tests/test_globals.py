"""Globals normalization tests, incl. whitespace preservation for aliasr_prefix.

Regression guard for issue #1: a command prefix like "proxychains -q " must keep
its trailing space, or builds concatenate as "proxychains -qnmap".
"""

from aliasr.core import globals as g
from aliasr.core.globals import _normalize_history_list


def test_normalize_strips_by_default():
    assert _normalize_history_list(["  10.0.0.1  "]) == ["10.0.0.1"]


def test_normalize_preserves_whitespace_when_asked():
    assert _normalize_history_list(["proxychains -q "], preserve_ws=True) == [
        "proxychains -q "
    ]


def test_aliasr_prefix_keeps_trailing_space_end_to_end():
    g.save_global("aliasr_prefix", "proxychains -q ")
    assert g.load_globals().get("aliasr_prefix") == "proxychains -q "


def test_other_globals_still_strip_end_to_end():
    g.save_global("ip", "  10.0.0.1  ")
    assert g.load_globals().get("ip") == "10.0.0.1"


def test_reorder_preserves_prefix_whitespace():
    # Reordering the globals grid re-normalizes every value; aliasr_prefix must
    # keep its significant trailing space, not get glued to the next command.
    g.save_global("aliasr_prefix", "proxychains -q ")
    g.save_global("ip", "10.0.0.1")
    g.save_globals_order(["ip", "aliasr_prefix"])
    assert g.load_globals().get("aliasr_prefix") == "proxychains -q "


def test_canonicalize_preserves_prefix_whitespace():
    canon = g._canonicalize({"aliasr_prefix": ["proxychains -q "], "ip": ["  1.2.3.4  "]})
    assert canon["aliasr_prefix"] == ["proxychains -q "]
    assert canon["ip"] == ["1.2.3.4"]
