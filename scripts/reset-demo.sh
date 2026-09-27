#!/usr/bin/env bash
# reset-demo.sh -- restore sample-magento/ from git and delete generated artefacts
# so the Magento Broker demo can be re-run from a clean state.
#
# Usage:
#   bash scripts/reset-demo.sh
#
# What it does:
#   1. Restores every file under sample-magento/ to its last committed state.
#   2. Removes findings.json, report.md, and fix-plan.md from the project root.
#
# Nothing outside sample-magento/ and the three artefact files is touched.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Restoring sample-magento/ from git..."
git checkout -- sample-magento/

echo "==> Removing generated artefacts..."
for f in findings.json report.md fix-plan.md; do
    if [ -f "$f" ]; then
        rm "$f"
        echo "    deleted $f"
    else
        echo "    $f not present, skipping"
    fi
done

echo "==> Done. sample-magento/ is clean and ready for a fresh scan."
