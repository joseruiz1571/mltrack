#!/usr/bin/env bash
# Demo 1 — Quick Start: inventory + compliance posture in under a minute.
cd "$(dirname "$0")" && source ./lib.sh

banner "mltrack — AI model governance for financial services, in your terminal"
say "Start with a populated inventory of deployed models."
run "mltrack sample-data --count 12 --clear"
say "What AI models are running across the firm?"
run "mltrack list"
say "Risk-based review cycles, aligned to SR 11-7. Who is overdue?"
run "mltrack validate --all"
say "Narrow to just the critical-risk models."
run "mltrack list --risk critical"
say "Inventory and compliance posture — in under a minute."
sleep 1
