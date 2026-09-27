"""
constraints.py — translate Composer constraint syntax to packaging.SpecifierSet.

Composer constraints supported:
  ^X.Y[.Z]   — caret (compatible with)
  ~X.Y.Z      — tilde (approximate)
  >=X.Y       — greater-or-equal (and other comparison operators)
  X.Y.Z       — exact
  *           — any
  expr || expr — OR of two constraint groups
"""

from __future__ import annotations

import re
from packaging.specifiers import SpecifierSet


def _parse_single(token: str) -> SpecifierSet:
    """Parse one Composer constraint token (no || inside)."""
    token = token.strip()

    if token == "" or token == "*":
        return SpecifierSet("")

    # Caret ^X.Y[.Z]
    m = re.fullmatch(r"\^(\d+)\.(\d+)(?:\.(\d+))?", token)
    if m:
        major, minor, patch_ = int(m.group(1)), int(m.group(2)), m.group(3)
        lower = f"{major}.{minor}.{patch_ or '0'}"
        upper_major = major + 1
        return SpecifierSet(f">={lower},<{upper_major}.0.0")

    # Tilde ~X.Y.Z — locks major.minor, allows patch bump
    m = re.fullmatch(r"~(\d+)\.(\d+)\.(\d+)", token)
    if m:
        major, minor, patch_ = m.group(1), m.group(2), m.group(3)
        next_minor = int(minor) + 1
        return SpecifierSet(f">={major}.{minor}.{patch_},<{major}.{next_minor}.0")

    # Tilde ~X.Y — locks major, allows minor bump
    m = re.fullmatch(r"~(\d+)\.(\d+)", token)
    if m:
        major, minor = m.group(1), m.group(2)
        next_major = int(major) + 1
        return SpecifierSet(f">={major}.{minor}.0,<{next_major}.0.0")

    # Comparison operators: >=, <=, >, <, !=, ==
    m = re.fullmatch(r"([><=!]+)\s*(\d[\d.]*)", token)
    if m:
        op, ver = m.group(1), m.group(2)
        # Normalise == to ==, map = to ==
        op = op.replace("=", "==").replace(">>>", ">=").replace("<<<", "<=")
        # Fix doubled == that wasn't already correct
        op = re.sub(r"={3,}", "==", op)
        return SpecifierSet(f"{op}{ver}")

    # Exact version X.Y.Z
    m = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?", token)
    if m:
        ver = token if m.group(3) else f"{token}.0"
        return SpecifierSet(f"=={ver}")

    # Fallback — return empty (matches anything) rather than crash
    return SpecifierSet("")


def parse_constraint(s: str) -> SpecifierSet:
    """
    Parse a Composer version constraint string and return a SpecifierSet.

    Handles: ^X.Y, ~X.Y.Z, >=X.Y, exact, *, and expr||expr groups.
    OR groups are returned as the *union* encoded as multiple SpecifierSets
    joined so that ``contains()`` returns True if any branch matches.
    Because packaging.SpecifierSet cannot represent OR natively we return
    a _UnionSpecifierSet wrapper that delegates contains() correctly.
    """
    parts = [p.strip() for p in s.split("||")]
    if len(parts) == 1:
        return _parse_single(parts[0])
    return _UnionSpecifierSet([_parse_single(p) for p in parts])


class _UnionSpecifierSet:
    """Minimal wrapper that allows OR-semantics for ``in`` checks."""

    def __init__(self, specs: list[SpecifierSet]) -> None:
        self._specs = specs

    def __contains__(self, version: str) -> bool:
        return any(version in s for s in self._specs)

    def __repr__(self) -> str:  # pragma: no cover
        return " || ".join(str(s) for s in self._specs)
