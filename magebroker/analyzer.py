"""
analyzer.py — detect bugs and issues in a Magento 2 project.

Public API:
    detect_version_conflicts(project)     -> list[Finding]
    detect_missing_deps(project)          -> list[Finding]
    detect_circular_sequences(graph)      -> list[Finding]
    detect_duplicate_preferences(project) -> list[Finding]
    detect_upgrade_blockers(project, target_version, compat) -> list[Finding]
    detect_ghost_sequences(project)       -> list[Finding]
    analyze(project, graph, target, compat) -> list[Finding]
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from magebroker.collector import Project
from magebroker.constraints import InvalidConstraint, parse_constraint


# ---------------------------------------------------------------------------
# Finding dataclass
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    id: str           # e.g. "B1"
    type: str         # e.g. "version_conflict"
    severity: str     # "critical" or "warning"
    module: str       # e.g. "Acme_Checkout"
    file: str         # relative file path hint
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _unparseable_finding(mod_name: str, mod: Any, constraint_str: str) -> Finding:
    """Return a warning finding for a constraint that could not be parsed."""
    return Finding(
        id="W0",
        type="unparseable_constraint",
        severity="warning",
        module=mod_name,
        file=str(mod.path / "composer.json"),
        message=(
            f"{mod_name} has a constraint that could not be parsed: "
            f"{constraint_str!r}"
        ),
        evidence={"constraint": constraint_str},
    )


# ---------------------------------------------------------------------------
# B1 — Version conflicts
# ---------------------------------------------------------------------------


def detect_version_conflicts(project: Project) -> list[Finding]:
    """
    For each locked package, check every module that requires it.
    If the locked version is NOT within the module's constraint, report a finding.
    """
    findings: list[Finding] = []

    for pkg_name, locked_pkg in project.locked.items():
        locked_version = locked_pkg.version
        for mod_name, mod in project.modules.items():
            for req_pkg, constraint_str in mod.requires.items():
                if req_pkg.lower() != pkg_name:
                    continue
                try:
                    spec = parse_constraint(constraint_str)
                except InvalidConstraint:
                    findings.append(_unparseable_finding(mod_name, mod, constraint_str))
                    continue
                if locked_version not in spec:
                    findings.append(Finding(
                        id="B1",
                        type="version_conflict",
                        severity="critical",
                        module=mod_name,
                        file=str(mod.path / "composer.json"),
                        message=(
                            f"{mod_name} requires {req_pkg} {constraint_str!r} "
                            f"but composer.lock has {locked_version}"
                        ),
                        evidence={
                            "package": pkg_name,
                            "locked_version": locked_version,
                            "constraint": constraint_str,
                        },
                    ))

    return findings


# ---------------------------------------------------------------------------
# B2 — Missing dependencies
# ---------------------------------------------------------------------------


def detect_missing_deps(project: Project) -> list[Finding]:
    """
    Report packages required by a module that are absent from composer.lock.
    Skips: php, ext-* packages, and anything already in the lock file.
    """
    findings: list[Finding] = []

    for mod_name, mod in project.modules.items():
        for pkg, constraint_str in mod.requires.items():
            pkg_lower = pkg.lower()
            # Skip php and PHP extensions
            if pkg_lower == "php" or pkg_lower.startswith("ext-"):
                continue
            if pkg_lower not in project.locked:
                findings.append(Finding(
                    id="B2",
                    type="missing_dep",
                    severity="critical",
                    module=mod_name,
                    file=str(mod.path / "composer.json"),
                    message=(
                        f"{mod_name} requires {pkg} {constraint_str!r} "
                        f"but it is not present in composer.lock"
                    ),
                    evidence={
                        "package": pkg,
                        "constraint": constraint_str,
                    },
                ))

    return findings


# ---------------------------------------------------------------------------
# B3 — Circular sequences
# ---------------------------------------------------------------------------


def detect_circular_sequences(graph: nx.DiGraph) -> list[Finding]:
    """
    Detect cycles in the sequence sub-graph (only "sequence" edges).
    Reports one Finding per cycle found.
    """
    seq_edges = [
        (u, v) for u, v, data in graph.edges(data=True)
        if data.get("rel") == "sequence"
    ]
    subgraph = nx.DiGraph()
    subgraph.add_nodes_from(graph.nodes())
    subgraph.add_edges_from(seq_edges)

    findings: list[Finding] = []
    try:
        cycle = nx.find_cycle(subgraph)
        first_node = cycle[0][0]
        cycle_str = " -> ".join(u for u, v in cycle) + f" -> {cycle[-1][1]}"
        findings.append(Finding(
            id="B3",
            type="circular_sequence",
            severity="critical",
            module=first_node,
            file="etc/module.xml",
            message=f"Circular sequence detected: {cycle_str}",
            evidence={"cycle": [(u, v) for u, v in cycle]},
        ))
    except nx.NetworkXNoCycle:
        pass

    return findings


# ---------------------------------------------------------------------------
# B4 — Duplicate DI preferences
# ---------------------------------------------------------------------------


def detect_duplicate_preferences(project: Project) -> list[Finding]:
    """
    Group all di.xml preferences by the 'for' interface across all modules.
    Emit ONE finding per conflicting interface, listing every module involved.
    """
    iface_modules: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for mod_name, mod in project.modules.items():
        for pref in mod.preferences:
            iface = pref.get("for", "")
            impl = pref.get("type", "")
            if iface:
                iface_modules[iface].append((mod_name, impl))

    findings: list[Finding] = []
    for iface, declarations in iface_modules.items():
        if len(declarations) > 1:
            module_list = ", ".join(m for m, _ in declarations)
            files = [
                str(project.modules[m].path / "etc" / "di.xml")
                for m, _ in declarations
            ]
            findings.append(Finding(
                id="B4",
                type="duplicate_preference",
                severity="warning",
                module=module_list,
                file=", ".join(files),
                message=(
                    f"Duplicate preference for {iface!r} declared in "
                    f"{len(declarations)} modules: {module_list}"
                ),
                evidence={
                    "interface": iface,
                    "all_implementations": [
                        {"module": m, "type": t} for m, t in declarations
                    ],
                },
            ))

    return findings


# ---------------------------------------------------------------------------
# B5 — Upgrade blockers
# ---------------------------------------------------------------------------


def detect_upgrade_blockers(
    project: Project,
    target_version: str,
    compat: dict,
) -> list[Finding]:
    """
    For each module that requires 'php', check whether any of the target
    Magento version's compatible PHP versions satisfies the constraint.
    If none do, report a blocker.

    compat format: { "2.4.7": ["8.2", "8.3"], ... }
    Each value is a list of PHP minor version strings like "8.2".
    """
    target_compat = compat.get(target_version, {})
    required_php_versions: list[str] = (
        target_compat.get("php", [])
        if isinstance(target_compat, dict)
        else target_compat
    )
    findings: list[Finding] = []

    for mod_name, mod in project.modules.items():
        for pkg, constraint_str in mod.requires.items():
            if pkg.lower() != "php":
                continue
            try:
                spec = parse_constraint(constraint_str)
            except InvalidConstraint:
                findings.append(_unparseable_finding(mod_name, mod, constraint_str))
                continue
            # Test representative versions: "8.2" -> "8.2.0"
            compatible = any(
                f"{ver}.0" in spec for ver in required_php_versions
            )
            if not compatible:
                findings.append(Finding(
                    id="B5",
                    type="upgrade_blocker",
                    severity="critical",
                    module=mod_name,
                    file=str(mod.path / "composer.json"),
                    message=(
                        f"{mod_name} requires php {constraint_str!r} which is "
                        f"incompatible with Magento {target_version} "
                        f"(needs PHP {required_php_versions})"
                    ),
                    evidence={
                        "php_constraint": constraint_str,
                        "target_magento_version": target_version,
                        "required_php_versions": required_php_versions,
                    },
                ))

    return findings


# ---------------------------------------------------------------------------
# B6 — Ghost sequences
# ---------------------------------------------------------------------------


# Well-known core Magento module names that commonly appear in sequences
# but may not be in composer.lock for every project.
_CORE_MAGENTO_MODULES: frozenset[str] = frozenset({
    "Magento_Catalog",
    "Magento_Store",
    "Magento_Checkout",
    "Magento_Customer",
    "Magento_Search",
    "Magento_Cms",
    "Magento_Sales",
    "Magento_Quote",
    "Magento_Payment",
    "Magento_Shipping",
    "Magento_Backend",
    "Magento_Config",
    "Magento_Directory",
    "Magento_Eav",
    "Magento_Theme",
    "Magento_Widget",
    "Magento_Reports",
    "Magento_Tax",
    "Magento_Newsletter",
    "Magento_Wishlist",
    "Magento_Review",
    "Magento_LayeredNavigation",
    "Magento_Inventory",
    "Magento_InventoryApi",
})


def _pkg_to_module_name(pkg_name: str) -> str | None:
    """
    Convert a locked package name like 'magento/module-catalog'
    to its Magento module name 'Magento_Catalog'.
    Returns None if the package doesn't match the module naming pattern.
    """
    prefix = "magento/module-"
    if not pkg_name.startswith(prefix):
        return None
    remainder = pkg_name[len(prefix):]  # e.g. "catalog" or "catalog-product"
    parts = remainder.split("-")
    return "Magento_" + "_".join(p.capitalize() for p in parts)


def detect_ghost_sequences(project: Project) -> list[Finding]:
    """
    Detect sequences referencing module names that don't exist in the project
    or as known core Magento modules (derived from composer.lock or the
    built-in allowlist).
    """
    known_modules: set[str] = set(project.modules.keys())

    # Derive module names from locked packages
    for pkg_name in project.locked:
        derived = _pkg_to_module_name(pkg_name)
        if derived:
            known_modules.add(derived)

    # Add well-known core modules
    known_modules |= _CORE_MAGENTO_MODULES

    findings: list[Finding] = []
    for mod_name, mod in project.modules.items():
        for seq_name in mod.sequences:
            if seq_name not in known_modules:
                findings.append(Finding(
                    id="B6",
                    type="ghost_sequence",
                    severity="warning",
                    module=mod_name,
                    file=str(mod.path / "etc" / "module.xml"),
                    message=(
                        f"{mod_name} sequences {seq_name!r} but that module "
                        f"does not exist in the project or in composer.lock"
                    ),
                    evidence={"ghost_module": seq_name},
                ))

    return findings


# ---------------------------------------------------------------------------
# Top-level entrypoint
# ---------------------------------------------------------------------------


def analyze(
    project: Project,
    graph: nx.DiGraph,
    target: str,
    compat: dict,
) -> list[Finding]:
    """Run all detectors and return a combined list of findings."""
    findings: list[Finding] = []
    findings.extend(detect_version_conflicts(project))
    findings.extend(detect_missing_deps(project))
    findings.extend(detect_circular_sequences(graph))
    findings.extend(detect_duplicate_preferences(project))
    findings.extend(detect_upgrade_blockers(project, target, compat))
    findings.extend(detect_ghost_sequences(project))
    return findings
