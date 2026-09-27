import dataclasses
import json
from pathlib import Path

from rich.console import Console
from rich.table import Table

from magebroker.analyzer import Finding

console = Console()


def render(findings: list, out_dir: Path) -> int:
    # --- Rich table to console ---
    table = Table(title="MageBroker Findings")
    table.add_column("Severity", style="bold", no_wrap=True)
    table.add_column("ID", no_wrap=True)
    table.add_column("Module", no_wrap=True)
    table.add_column("Message", overflow="fold")

    for f in findings:
        if f.severity == "critical":
            style = "red"
        elif f.severity == "warning":
            style = "yellow"
        else:
            style = None
        table.add_row(f.severity, f.id, f.module, f.message, style=style)

    console.print(table)

    # --- Health score ---
    score = 100
    for f in findings:
        if f.severity == "critical":
            score -= 20
        elif f.severity == "warning":
            score -= 5
    score = max(score, 0)

    console.print(f"Health score: {score} / 100")

    # --- findings.json ---
    out_dir.mkdir(parents=True, exist_ok=True)
    findings_path = out_dir / "findings.json"
    findings_path.write_text(
        json.dumps([dataclasses.asdict(f) for f in findings], indent=2),
        encoding="utf-8",
    )

    # --- report.md ---
    lines = [
        "# MageBroker Report",
        "",
        "| Severity | ID | Module | Message |",
        "| --- | --- | --- | --- |",
    ]
    for f in findings:
        msg = f.message.replace("|", "\\|")
        lines.append(f"| {f.severity} | {f.id} | {f.module} | {msg} |")

    lines += [
        "",
        f"**Health score: {score} / 100**",
        "",
    ]

    report_path = out_dir / "report.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")

    return score
