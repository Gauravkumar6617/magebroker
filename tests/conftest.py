import json
from pathlib import Path
import pytest
from magebroker.collector import collect
from magebroker.graph import build_graph

SAMPLE = Path(__file__).parent.parent / "sample-magento"
CLEAN = Path(__file__).parent / "fixtures" / "clean-magento"
COMPAT_PATH = Path(__file__).parent.parent / "data" / "compat.json"


@pytest.fixture(scope="session")
def compat():
    return json.loads(COMPAT_PATH.read_text())


@pytest.fixture(scope="session")
def project():
    return collect(SAMPLE)


@pytest.fixture(scope="session")
def graph(project):
    return build_graph(project)


@pytest.fixture(scope="session")
def clean_project():
    return collect(CLEAN)


@pytest.fixture(scope="session")
def clean_graph(clean_project):
    return build_graph(clean_project)
