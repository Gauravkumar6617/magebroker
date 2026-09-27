# MageBroker Plan

## Overview

Build **MageBroker**, a fully-offline Magento 2 dependency broker CLI tool that scans a project and produces an AI-generated fix plan.  
The project is split into three self-contained phases:

- **Phase 1** – Scaffold the sample Magento project and compatibility data
- **Phase 2** – Build the Python scanner package and pytest suite
- **Phase 3** – Add the Bob custom mode, README, and pyproject.toml packaging

Stack: Python 3.10+, Typer, Rich, networkx, packaging.
Bob custom-mode file: `.bob/custom_modes.yaml` (project-scoped).

> **Corrections applied (post-review):**
> - (a) `packaging` cannot parse Composer constraint syntax. Add `magebroker/constraints.py` to translate `^`, `~`, `*`, `||`, `>=`, exact into `SpecifierSet`. B1 and B5 use it.
> - (b) `composer.lock` must include every `magento/module-*` package referenced by sample modules so core modules are never falsely flagged as ghost/missing. Map `magento/module-catalog` ↔ `Magento_Catalog`, etc.
> - (c) `data/compat.json`: 2.4.6 → framework `103.0.6`, PHP `["8.1","8.2"]`; 2.4.7 → framework `103.0.7`, PHP `["8.2","8.3"]`. Lock file pins framework at `103.0.6`.
> - (d) Tests: add `tests/fixtures/clean-magento/` (no bugs) and a test asserting zero findings + exit code 0.
> - (e) Architecture mermaid diagram goes in README (Phase 3), not the plan.

---

## Full File Tree

```
magebroker/
├── .bob/
│   └── custom_modes.yaml                  # Bob "Magento Broker" custom mode
├── data/
│   └── compat.json                        # PHP + framework compat matrix
├── sample-magento/
│   ├── composer.json                      # Root Magento 2.4.6 project
│   ├── composer.lock                      # Locked packages (includes deliberate gaps)
│   ├── BUGS.md                            # Documents B1-B6 with file locations
│   └── app/code/Acme/
│       ├── Catalog/
│       │   ├── composer.json
│       │   ├── registration.php
│       │   ├── etc/module.xml
│       │   └── etc/di.xml
│       ├── Checkout/
│       │   ├── composer.json
│       │   ├── registration.php
│       │   ├── etc/module.xml
│       │   └── etc/di.xml
│       ├── Customer/
│       │   ├── composer.json
│       │   ├── registration.php
│       │   ├── etc/module.xml
│       │   └── etc/di.xml
│       ├── Inventory/
│       │   ├── composer.json
│       │   ├── registration.php
│       │   ├── etc/module.xml
│       │   └── etc/di.xml
│       ├── Payment/
│       │   ├── composer.json
│       │   ├── registration.php
│       │   ├── etc/module.xml
│       │   └── etc/di.xml
│       └── Search/
│           ├── composer.json
│           ├── registration.php
│           ├── etc/module.xml
│           └── etc/di.xml
├── magebroker/
│   ├── __init__.py
│   ├── constraints.py              # Composer → packaging SpecifierSet translator
│   ├── collector.py
│   ├── graph.py
│   ├── analyzer.py
│   ├── report.py
│   └── cli.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_analyzer.py
│   └── fixtures/
│       └── clean-magento/          # Zero-bug fixture for exit-code-0 test
├── pyproject.toml
├── README.md
└── magebroker-plan.md
```

---

## Phase 1 — Sample Project + Data

### Intent
Create the fake Magento 2.4.6 project that serves as the concrete test input for all detectors.  
Every bug must be present in real files so tests and manual `magebroker scan` both exercise it.

### Bugs planted

| ID | Type | Where planted |
|----|------|---------------|
| B1 | Version conflict | `Acme_Catalog/composer.json` requires `magento/framework ^103.0`, `Acme_Checkout/composer.json` requires `magento/framework ^102.0` — root `composer.lock` locks `103.0.6` |
| B2 | Missing dependency | `Acme_Payment/composer.json` requires `acme/payment-gateway ^1.0`; package absent from `composer.lock` |
| B3 | Circular sequence | `Acme_Catalog/etc/module.xml` sequences `Acme_Checkout`; `Acme_Checkout/etc/module.xml` sequences `Acme_Catalog` |
| B4 | Duplicate DI preference | `Acme_Catalog/etc/di.xml` and `Acme_Customer/etc/di.xml` both declare `<preference for="Magento\Catalog\Api\ProductRepositoryInterface">` |
| B5 | Upgrade blocker | `Acme_Inventory/composer.json` requires `php ~8.1.0`; target 2.4.7 needs PHP 8.2/8.3 |
| B6 | Ghost sequence | `Acme_Search/etc/module.xml` sequences `Acme_Analytics` which has no module directory |

### Expected Outcomes
- `sample-magento/` directory exists with all 6 modules, root `composer.json`, `composer.lock`
- `sample-magento/BUGS.md` documents each bug with exact file path + line
- `data/compat.json` exists with PHP and `magento/framework` version ranges for 2.4.6 and 2.4.7

### Todo List
- [ ] Create `data/compat.json` with compat matrix for 2.4.6 and 2.4.7
- [ ] Create root `sample-magento/composer.json` (Magento 2.4.6 project skeleton)
- [ ] Create root `sample-magento/composer.lock` (locked packages; include `magento/framework 103.0.6` + all referenced `magento/module-*` packages; omit `acme/payment-gateway`)
- [ ] Create `Acme_Catalog` module files (plant B1 version conflict in composer.json, plant B3 circular sequence in module.xml, plant B4 duplicate preference in di.xml)
- [ ] Create `Acme_Checkout` module files (plant B1 other side + B3 other side)
- [ ] Create `Acme_Customer` module files (plant B4 other side)
- [ ] Create `Acme_Payment` module files (plant B2 missing dep in composer.json)
- [ ] Create `Acme_Inventory` module files (plant B5 PHP constraint)
- [ ] Create `Acme_Search` module files (plant B6 ghost sequence)
- [ ] Write `sample-magento/BUGS.md`

### Status
`[ ] pending`

---

## Phase 2 — Scanner Package + Tests

### Intent
Build the `magebroker` Python package and a pytest suite that proves each of B1–B6 is detected.

### Sub-tasks

#### 2a — collector.py
**Intent:** Parse all relevant files into typed dataclasses so the rest of the code never touches raw JSON/XML.

Dataclasses to define:
- `ComposerProject` (root composer.json + lock)
- `LockedPackage` (name, version, from lock)
- `Module` (name, path, composer requires, sequences, preferences)

Parsing targets: root `composer.json`, `composer.lock`, per-module `composer.json`, `etc/module.xml`, `etc/di.xml`.

**Expected Outcomes:** `collector.py` exports a `collect(root_path) -> Project` function returning a fully-populated project object.

**Todo List**
- [ ] Define dataclasses: `LockedPackage`, `ModuleInfo`, `Project`
- [ ] Implement root `composer.json` and `composer.lock` parsing
- [ ] Implement module discovery (walk `app/code/*/*/`)
- [ ] Implement per-module `composer.json` parsing
- [ ] Implement `module.xml` parsing (name, sequence list)
- [ ] Implement `di.xml` parsing (list of `<preference for=... type=...>`)
- [ ] Export top-level `collect(root_path: Path) -> Project`

**Status:** `[ ] pending`

#### 2b — graph.py
**Intent:** Build a `networkx.DiGraph` of module/package relationships for cycle detection and dependency traversal.

Nodes: modules + packages. Edges: `sequence`, `requires`, `provides`.

**Expected Outcomes:** `build_graph(project) -> nx.DiGraph` with typed edge attributes.

**Todo List**
- [ ] Add module nodes and sequence edges
- [ ] Add package nodes and `requires` edges from each module's composer.json
- [ ] Export `build_graph(project) -> nx.DiGraph`

**Status:** `[ ] pending`

#### 2b.5 — constraints.py
**Intent:** Translate Composer version constraint strings into `packaging.specifiers.SpecifierSet` objects so B1/B5 detectors can use standard Python semver range arithmetic. Composer's `^`, `~`, `*`, `||`, `>=`, and exact forms do not map 1:1 to PEP 440.

**Expected Outcomes:** `parse_constraint(s: str) -> SpecifierSet` handles all Composer constraint forms used in the sample project.

**Todo List**
- [ ] Implement `parse_constraint` for `^X.Y`, `~X.Y.Z`, `>=X.Y`, `*`, `||`, exact versions
- [ ] Unit-test the translator with sample strings

**Status:** `[ ] pending`

#### 2c — analyzer.py
**Intent:** One detector function per bug type; each returns a list of finding dicts.

Finding schema: `{id, type, severity, module, file, message, evidence}`.
Severity: `critical` (blocks release) or `warning`.

Detectors:
- `detect_version_conflicts(project)` → B1; uses `constraints.parse_constraint` + `packaging`; severity `critical`
- `detect_missing_deps(project)` → B2; cross-checks composer requires vs lock; severity `critical`
- `detect_circular_sequences(graph)` → B3; `nx.find_cycle()`; severity `critical`
- `detect_duplicate_preferences(project)` → B4; group by interface, flag duplicates; severity `warning`
- `detect_upgrade_blockers(project, target_version, compat)` → B5; uses `constraints.parse_constraint`; severity `critical`
- `detect_ghost_sequences(project)` → B6; sequence names not in known module set; severity `warning`
- Top-level `analyze(project, graph, target, compat) -> list[Finding]`

**Expected Outcomes:** Each detector returns correctly-typed findings for sample-magento inputs.

**Todo List**
- [ ] Define `Finding` dataclass
- [ ] Implement `detect_version_conflicts`
- [ ] Implement `detect_missing_deps`
- [ ] Implement `detect_circular_sequences`
- [ ] Implement `detect_duplicate_preferences`
- [ ] Implement `detect_upgrade_blockers`
- [ ] Implement `detect_ghost_sequences`
- [ ] Implement top-level `analyze()`

**Status:** `[ ] pending`

#### 2d — report.py
**Intent:** Render findings to terminal (Rich table), write `findings.json`, write `report.md`, compute health score.

Health score formula: start 100, subtract per finding by severity (e.g. −20 critical, −5 warning), floor 0.

**Expected Outcomes:** After `render(findings, out_dir)`, three artefacts exist and health score is printed.

**Todo List**
- [ ] Implement Rich table output (columns: severity, type, module, message)
- [ ] Write `findings.json` (list of Finding dicts)
- [ ] Write `report.md` (Markdown table + health score)
- [ ] Compute and print health score

**Status:** `[ ] pending`

#### 2e — cli.py
**Intent:** Typer CLI entry point. `magebroker scan <path> [--target 2.4.7]`. Exit code 1 if any critical findings.

**Expected Outcomes:** `magebroker scan sample-magento/ --target 2.4.7` prints table, writes artefacts, exits 1.

**Todo List**
- [ ] Define `scan` Typer command with `path` arg and `--target` option (default `2.4.6`)
- [ ] Load `data/compat.json` relative to package
- [ ] Orchestrate: collect → build_graph → analyze → render → exit code

**Status:** `[ ] pending`

#### 2f — pyproject.toml
**Intent:** Standard packaging so `pip install -e .` works and `magebroker` is on PATH.

**Todo List**
- [ ] Write `pyproject.toml` with `[project]` metadata, dependencies (typer, rich, networkx, packaging), and `[project.scripts]` entry point

**Status:** `[ ] pending`

#### 2g — tests
**Intent:** One pytest test per bug (B1–B6) using the sample-magento fixture, proving each detector fires. Plus a clean-magento fixture asserting zero findings and exit code 0.

**Todo List**
- [ ] `conftest.py`: `project` and `graph` fixtures pointing at `sample-magento/`; separate `clean_project` fixture pointing at `tests/fixtures/clean-magento/`
- [ ] `test_analyzer.py`: six test functions, one per bug, asserting finding type and module name
- [ ] `test_clean.py`: asserts `analyze()` returns empty list for clean-magento; asserts CLI exits 0
- [ ] Create `tests/fixtures/clean-magento/` with minimal valid Magento project (no bugs)
- [ ] Confirm all 7 pass with `pytest -q`

**Status:** `[ ] pending`

---

## Phase 3 — Bob Custom Mode + README

### Intent
Deliver the Bob "Magento Broker" custom mode and project README.

#### 3a — Bob custom mode
**Intent:** A project-scoped Bob mode that reads `findings.json`, spawns one subagent per finding type in parallel, writes `fix-plan.md`, applies safe fixes, then re-runs the scan to verify.

File: `.bob/custom_modes.yaml`  
Format: YAML `customModes` array (per Bob docs).  
Groups needed: `read`, `edit`, `execute`, `subagent`, `skill`.

Role definition summary:
- Read `findings.json` produced by the CLI
- For each distinct finding `type`, spawn a subagent to draft the fix commands/edits
- Merge subagent outputs into ordered `fix-plan.md` (composer commands first, then file edits)
- Safe auto-fixes (applied directly to files):
  - B1: align the module's constraint to match the locked version
  - B3: remove one direction of the circular sequence entry
  - B4: remove the duplicate `<preference>` block
  - B5: widen php constraint to `"~8.2.0||~8.3.0"`
  - B6: remove the ghost `<module>` entry from sequence
- B2 cannot be fixed offline → marked "manual" in `fix-plan.md` with the `composer require` command
- Re-run `magebroker scan` to verify: expected result is 5 fixed, 1 manual (B2 still present)

**Expected Outcomes:** `.bob/custom_modes.yaml` is valid YAML; the mode is selectable in Bob UI.

**Todo List**
- [ ] Write `.bob/custom_modes.yaml` with `magento-broker` slug, role definition, custom instructions, and tool groups

**Status:** `[ ] pending`

#### 3b — README
**Intent:** One-page README covering install, usage, sample output, and how to use the Bob mode.

**Todo List**
- [ ] Write `README.md` with: project description, install steps, `magebroker scan` usage, Bob mode usage, bug list reference

**Status:** `[ ] pending`

---

## Implementation Notes

- `constraints.py` translates Composer constraint syntax to `SpecifierSet` before any `packaging` calls; B1 and B5 detectors use it.
- `networkx.find_cycle()` detects B3 on the sequence sub-graph.
- `data/compat.json` is loaded at runtime by `cli.py`; path resolved via `__file__`-relative lookup.
- `composer.lock` includes `magento/module-catalog`, `magento/module-checkout`, `magento/module-customer`, `magento/module-inventory`, `magento/module-search` etc. so the collector can map Composer package names ↔ Magento module names without false positives.
- No network calls anywhere — all data is local files.
- The Bob custom mode uses project-level `.bob/custom_modes.yaml` so it is repo-portable.
- Architecture mermaid diagram lives in README (not in this plan file).
