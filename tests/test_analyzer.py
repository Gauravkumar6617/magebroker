from pathlib import Path

import networkx as nx
import pytest

from magebroker.analyzer import (
    detect_version_conflicts,
    detect_missing_deps,
    detect_circular_sequences,
    detect_duplicate_preferences,
    detect_upgrade_blockers,
    detect_ghost_sequences,
    analyze,
)
from magebroker.collector import LockedPackage, ModuleInfo, Project


def test_b1_version_conflict(project):
    findings = detect_version_conflicts(project)
    types = [f.type for f in findings]
    modules = [f.module for f in findings]
    assert "version_conflict" in types
    assert "Acme_Checkout" in modules  # ^102.0 conflicts with locked 103.0.6


def test_b2_missing_dep(project):
    findings = detect_missing_deps(project)
    assert any(f.type == "missing_dep" and f.module == "Acme_Payment" for f in findings)


def test_b3_circular_sequence(graph):
    findings = detect_circular_sequences(graph)
    assert len(findings) >= 1
    assert all(f.type == "circular_sequence" for f in findings)


def test_b4_duplicate_preference(project):
    findings = detect_duplicate_preferences(project)
    # B4 emits ONE finding per conflicting interface (both modules in one row)
    assert len(findings) == 1
    f = findings[0]
    assert f.type == "duplicate_preference"
    # Both offending modules must appear in the single finding
    assert "Acme_Catalog" in f.module
    assert "Acme_Customer" in f.module
    # Evidence lists both implementations
    assert len(f.evidence["all_implementations"]) == 2


def test_b5_upgrade_blocker(project, compat):
    findings = detect_upgrade_blockers(project, "2.4.7", compat)
    assert any(f.type == "upgrade_blocker" and f.module == "Acme_Inventory" for f in findings)


def test_b6_ghost_sequence(project):
    findings = detect_ghost_sequences(project)
    assert any(f.type == "ghost_sequence" and f.module == "Acme_Search" for f in findings)


def test_clean_fixture_zero_findings(clean_project, clean_graph, compat):
    findings = analyze(clean_project, clean_graph, "2.4.7", compat)
    assert findings == [], f"Expected 0 findings, got: {findings}"


# ---------------------------------------------------------------------------
# Unparseable constraint (e.g. dev-master) does not crash scan
# ---------------------------------------------------------------------------

@pytest.fixture()
def dev_master_project(tmp_path):
    """A minimal project where one module requires a dev-master branch."""
    mod_path = tmp_path / "app" / "code" / "Acme" / "DevTest"
    mod_path.mkdir(parents=True)
    mod = ModuleInfo(
        name="Acme_DevTest",
        path=mod_path,
        composer_name="acme/module-devtest",
        requires={"acme/some-lib": "dev-master"},
        sequences=[],
        preferences=[],
    )
    locked = {
        "acme/some-lib": LockedPackage(name="acme/some-lib", version="1.0.0"),
    }
    return Project(
        root=tmp_path,
        magento_version="2.4.7",
        root_requires={},
        locked=locked,
        modules={"Acme_DevTest": mod},
    )


def test_dev_master_emits_warning_not_crash(dev_master_project, compat):
    """Scan must complete; a dev-master constraint yields unparseable_constraint."""
    graph = nx.DiGraph()
    findings = analyze(dev_master_project, graph, "2.4.7", compat)
    types = [f.type for f in findings]
    assert "unparseable_constraint" in types, (
        f"Expected unparseable_constraint warning, got: {types}"
    )
    # Scan must not have raised — if we reach here it didn't crash
    unparseable = [f for f in findings if f.type == "unparseable_constraint"]
    assert unparseable[0].severity == "warning"
    assert unparseable[0].module == "Acme_DevTest"
    assert "dev-master" in unparseable[0].evidence["constraint"]
