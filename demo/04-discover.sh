#!/usr/bin/env bash
# Demo 4 — Registry discovery: find shadow AI before the auditors do.
cd "$(dirname "$0")" && source ./lib.sh

banner "mltrack — registry discovery (find untracked models)"
say "Shadow AI is the governance problem: models nobody put on the inventory."
run "mltrack sample-data --count 8 --clear"
say "Scan an external model registry (here, a mock MLflow source)."
run "mltrack discover --source mock"
say "Models in the registry, zero in governance. That gap is the risk."
sleep 1
