"""
graph.py — build a networkx DiGraph of module/package relationships.

Public API:
    build_graph(project: Project) -> nx.DiGraph
"""

from __future__ import annotations

import networkx as nx

from magebroker.collector import Project


def build_graph(project: Project) -> nx.DiGraph:
    """
    Build a directed graph from the project.

    Node types (stored in node attribute ``kind``):
        "module"  — a Magento module
        "package" — a Composer package

    Edge types (stored in edge attribute ``rel``):
        "sequence" — module A sequences module B (module.xml)
        "requires" — module A requires package B (composer.json)
    """
    g: nx.DiGraph = nx.DiGraph()

    # Add module nodes
    for name, mod in project.modules.items():
        g.add_node(name, kind="module", path=str(mod.path))

    # Add sequence edges between modules
    for name, mod in project.modules.items():
        for seq in mod.sequences:
            if not g.has_node(seq):
                g.add_node(seq, kind="module")
            g.add_edge(name, seq, rel="sequence")

    # Add package nodes and requires edges
    for name, mod in project.modules.items():
        for pkg, constraint in mod.requires.items():
            pkg_lower = pkg.lower()
            if not g.has_node(pkg_lower):
                g.add_node(pkg_lower, kind="package")
            g.add_edge(name, pkg_lower, rel="requires", constraint=constraint)

    return g
