"""
constraints.py -- translate Composer constraint syntax to packaging.SpecifierSet.

Composer constraints supported:
  ^X.Y[.Z]        -- caret (compatible with); ^0.x: >=0.x.0,<0.(x+1).0
  ~X.Y.Z          -- tilde (approximate)
  ~X.Y            -- tilde minor
  >=X.Y, <=X.Y, >X.Y, <X.Y, !=X.Y, ==X.Y, =X.Y  -- comparisons
  X.Y.Z           -- exact
  *               -- any
  expr expr       -- AND range (space-separated, e.g. ">=8.1 <8.4")
  expr,expr       -- AND range (comma-separated, e.g. ">=8.1,<8.4")
  expr || expr    -- OR of two constraint groups

Patch-level Magento versions (e.g. "103.0.6-p3") are normalised to "103.0.6"
before parsing so they compare correctly against SpecifierSets.

Unknown tokens do NOT silently match everything; parse_constraint() raises
InvalidConstraint so callers can surface a warning finding.
"""

from __future__ import annotations

import re
from packaging.specifiers import SpecifierSet


class InvalidConstraint(ValueError):
    """Raised when a constraint token cannot be parsed."""


def _strip_patch_label(version: str) -> str:
    """Remove Magento patch labels like '-p3' from version strings."""
    return re.sub(r"-p\d+$", "", version)


def _parse_single_token(token: str) -> SpecifierSet:
    """
    Parse ONE atomic Composer constraint token (no AND/OR inside).

    Raises InvalidConstraint for unrecognised tokens.
    """
    token = token.strip()
    token = _strip_patch_label(token)

    if token == "" or token == "*":
        return SpecifierSet("")

    # Caret ^X.Y[.Z] ----------------------------------------------------------
    # ^0.x semantics: >=0.x.0,<0.(x+1).0   (minor, not major, is the ceiling)
    m = re.fullmatch(r"\^(\d+)\.(\d+)(?:\.(\d+))?", token)
    if m:
        major, minor, patch_ = int(m.group(1)), int(m.group(2)), m.group(3)
        lower = f"{major}.{minor}.{patch_ or '0'}"
        if major == 0:
            # ^0.y.z -> >=0.y.0, <0.(y+1).0
            upper = f"0.{minor + 1}.0"
        else:
            upper = f"{major + 1}.0.0"
        return SpecifierSet(f">={lower},<{upper}")

    # Tilde ~X.Y.Z -- locks major.minor, allows patch bump --------------------
    m = re.fullmatch(r"~(\d+)\.(\d+)\.(\d+)", token)
    if m:
        major, minor, patch_ = m.group(1), m.group(2), m.group(3)
        next_minor = int(minor) + 1
        return SpecifierSet(f">={major}.{minor}.{patch_},<{major}.{next_minor}.0")

    # Tilde ~X.Y -- locks major, allows minor bump ----------------------------
    m = re.fullmatch(r"~(\d+)\.(\d+)", token)
    if m:
        major, minor = m.group(1), m.group(2)
        next_major = int(major) + 1
        return SpecifierSet(f">={major}.{minor}.0,<{next_major}.0.0")

    # Comparison operators: >=, <=, >, <, !=, ==, = --------------------------
    m = re.fullmatch(r"([><!]=?|==|!=|=)\s*(\d[\d.]*)", token)
    if m:
        op, ver = m.group(1), m.group(2)
        ver = _strip_patch_label(ver)
        # Map bare "=" to "==" without corrupting ">=" or "<=" or "!="
        if op == "=":
            op = "=="
        return SpecifierSet(f"{op}{ver}")

    # Exact version X.Y.Z or X.Y ---------------------------------------------
    m = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?", token)
    if m:
        ver = token if m.group(3) else f"{token}.0"
        return SpecifierSet(f"=={ver}")

    raise InvalidConstraint(f"Cannot parse Composer constraint token: {token!r}")


def _parse_and_group(s: str) -> SpecifierSet:
    """
    Parse a single AND group -- may be comma-separated or space-separated
    but contains no '||'.

    Example inputs:
        ">=8.1 <8.4"
        ">=8.1,<8.4"
        "^103.0"
    """
    s = s.strip()
    # Split on comma and/or whitespace sequences between tokens
    # Tokens start with a digit or an operator character
    raw_tokens = re.split(r"[,\s]+(?=[><=!^~\d\*])", s)
    specs: list[str] = []
    for raw in raw_tokens:
        raw = raw.strip()
        if not raw:
            continue
        ss = _parse_single_token(raw)  # may raise InvalidConstraint
        specs.append(str(ss))
    # Merge all into a single SpecifierSet (intersection / AND)
    combined = ",".join(specs)
    return SpecifierSet(combined)


def parse_constraint(s: str) -> "_ConstraintSpec":
    """
    Parse a Composer version constraint string and return an object that
    supports ``version in spec`` checks.

    Handles: ^X.Y, ~X.Y.Z, >=X.Y, exact, *, AND ranges (space/comma), and
    expr||expr groups.

    Raises InvalidConstraint for completely unrecognised syntax.
    """
    parts = [p.strip() for p in s.split("||")]
    parsed = [_parse_and_group(p) for p in parts if p.strip()]
    if len(parsed) == 1:
        return _WrappedSpecifierSet(parsed[0])
    return _UnionSpecifierSet(parsed)


# ---------------------------------------------------------------------------
# Wrappers that normalise patch labels before delegating to SpecifierSet
# ---------------------------------------------------------------------------

_ConstraintSpec = "_WrappedSpecifierSet | _UnionSpecifierSet"


class _WrappedSpecifierSet:
    """Single-branch wrapper that strips Magento patch labels before checking."""

    def __init__(self, spec: SpecifierSet) -> None:
        self._spec = spec

    def __contains__(self, version: str) -> bool:
        return _strip_patch_label(version) in self._spec

    def __repr__(self) -> str:  # pragma: no cover
        return str(self._spec)


class _UnionSpecifierSet:
    """Minimal wrapper that allows OR-semantics for ``in`` checks."""

    def __init__(self, specs: list[SpecifierSet]) -> None:
        self._specs = specs

    def __contains__(self, version: str) -> bool:
        version = _strip_patch_label(version)
        return any(version in s for s in self._specs)

    def __repr__(self) -> str:  # pragma: no cover
        return " || ".join(str(s) for s in self._specs)
