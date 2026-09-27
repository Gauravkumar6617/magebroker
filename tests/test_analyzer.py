from magebroker.analyzer import (
    detect_version_conflicts,
    detect_missing_deps,
    detect_circular_sequences,
    detect_duplicate_preferences,
    detect_upgrade_blockers,
    detect_ghost_sequences,
    analyze,
)


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
