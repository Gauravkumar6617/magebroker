"""
collector.py — parse a Magento 2 project tree into typed dataclasses.

Public API:
    collect(root_path: Path) -> Project
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class LockedPackage:
    name: str
    version: str


@dataclass
class ModuleInfo:
    name: str           # e.g. "Acme_Catalog"
    path: Path          # absolute path to module root
    composer_name: str  # e.g. "acme/module-catalog"
    requires: dict[str, str] = field(default_factory=dict)   # pkg -> constraint
    sequences: list[str] = field(default_factory=list)        # module names
    preferences: list[dict[str, str]] = field(default_factory=list)  # {for, type}


@dataclass
class Project:
    root: Path
    magento_version: str                              # from root composer.json
    root_requires: dict[str, str]                    # root composer.json require
    locked: dict[str, LockedPackage]                 # name -> LockedPackage
    modules: dict[str, ModuleInfo]                   # module_name -> ModuleInfo


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _parse_module_xml(path: Path) -> tuple[str, list[str]]:
    """Return (module_name, [sequenced_module_names])."""
    tree = ET.parse(path)
    root = tree.getroot()
    module_el = root.find("module")
    if module_el is None:
        return "", []
    name = module_el.get("name", "")
    seq_el = module_el.find("sequence")
    sequences: list[str] = []
    if seq_el is not None:
        for child in seq_el:
            n = child.get("name", "")
            if n:
                sequences.append(n)
    return name, sequences


def _parse_di_xml(path: Path) -> list[dict[str, str]]:
    """Return list of {for, type} preference dicts."""
    try:
        tree = ET.parse(path)
    except ET.ParseError:
        return []
    root = tree.getroot()
    prefs = []
    for pref in root.iter("preference"):
        for_iface = pref.get("for", "")
        impl_type = pref.get("type", "")
        if for_iface:
            prefs.append({"for": for_iface, "type": impl_type})
    return prefs


# ---------------------------------------------------------------------------
# Locked package parsing
# ---------------------------------------------------------------------------


def _parse_lock(lock_path: Path) -> dict[str, LockedPackage]:
    data = _load_json(lock_path)
    result: dict[str, LockedPackage] = {}
    for pkg in data.get("packages", []) + data.get("packages-dev", []):
        name = pkg["name"].lower()
        result[name] = LockedPackage(name=name, version=pkg.get("version", "0.0.0"))
    return result


# ---------------------------------------------------------------------------
# Module discovery
# ---------------------------------------------------------------------------


def _discover_modules(root: Path) -> list[Path]:
    """Return list of module root paths (directories containing etc/module.xml)."""
    code_dir = root / "app" / "code"
    if not code_dir.is_dir():
        return []
    found = []
    for module_xml in code_dir.rglob("etc/module.xml"):
        found.append(module_xml.parent.parent)
    return found


def _parse_module(module_path: Path) -> ModuleInfo | None:
    module_xml = module_path / "etc" / "module.xml"
    if not module_xml.exists():
        return None

    name, sequences = _parse_module_xml(module_xml)
    if not name:
        return None

    # composer.json (optional per module)
    composer_name = name.lower().replace("_", "-").replace("acme-", "acme/module-")
    requires: dict[str, str] = {}
    composer_json = module_path / "composer.json"
    if composer_json.exists():
        data = _load_json(composer_json)
        composer_name = data.get("name", composer_name)
        requires = data.get("require", {})

    # di.xml (optional)
    di_xml = module_path / "etc" / "di.xml"
    preferences = _parse_di_xml(di_xml) if di_xml.exists() else []

    return ModuleInfo(
        name=name,
        path=module_path,
        composer_name=composer_name,
        requires=requires,
        sequences=sequences,
        preferences=preferences,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def collect(root_path: Path) -> Project:
    """Parse a Magento 2 project tree rooted at *root_path* into a Project."""
    root = root_path.resolve()

    # Root composer.json
    root_composer = _load_json(root / "composer.json")
    root_requires: dict[str, str] = root_composer.get("require", {})

    # Determine installed Magento version from root require
    magento_version = root_requires.get(
        "magento/product-community-edition",
        root_requires.get("magento/product-enterprise-edition", "unknown"),
    )

    # composer.lock
    lock_path = root / "composer.lock"
    locked = _parse_lock(lock_path) if lock_path.exists() else {}

    # Discover and parse modules
    modules: dict[str, ModuleInfo] = {}
    for mod_path in _discover_modules(root):
        info = _parse_module(mod_path)
        if info:
            modules[info.name] = info

    return Project(
        root=root,
        magento_version=magento_version,
        root_requires=root_requires,
        locked=locked,
        modules=modules,
    )
