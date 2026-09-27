import json
from pathlib import Path

import typer

from magebroker.collector import collect
from magebroker.graph import build_graph
from magebroker.analyzer import analyze
from magebroker import report

app = typer.Typer()


@app.command("version")
def version_cmd() -> None:
    """Print the magebroker version."""
    import magebroker
    typer.echo(magebroker.__version__)


@app.command("scan")
def scan(
    path: Path = typer.Argument(..., help="Magento project root"),
    target: str = typer.Option("2.4.6", help="Target Magento version"),
    out: Path = typer.Option(Path("."), help="Output directory for findings.json and report.md"),
) -> None:
    """Scan a Magento 2 project for dependency and compatibility issues."""
    typer.echo(f"Scanning {path} (target: {target})...")

    compat_path = Path(__file__).parent.parent / "data" / "compat.json"
    compat = json.loads(compat_path.read_text(encoding="utf-8"))

    project = collect(path)
    graph = build_graph(project)
    findings = analyze(project, graph, target, compat)

    report.render(findings, out)

    if any(f.severity == "critical" for f in findings):
        raise typer.Exit(code=1)
