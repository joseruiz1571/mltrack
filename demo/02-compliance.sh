#!/usr/bin/env bash
# Demo 2 — Compliance workflow: from inventory to audit-ready report.
cd "$(dirname "$0")" && source ./lib.sh

banner "mltrack — compliance workflow"
say "Generate an inventory where some reviews have gone overdue."
run "mltrack sample-data --count 15 --clear --overdue-percent 30"
say "Validate every model against its required review cycle."
run "mltrack validate --all"
say "Produce the overdue-review report auditors ask for."
run "mltrack report compliance"
say "Compliance as data — not a spreadsheet someone forgot to update."
sleep 1
